from __future__ import annotations
"""
Risk Engine — Phase 4
=====================
All position sizing, portfolio-level guardrails, and exit logic lives here.
Nothing trades without passing through this module.

Components:
  KellyCriterion      — optimal fractional position sizing from win rate + avg PnL
  VaRGuard            — portfolio Value-at-Risk cap (historical simulation)
  DrawdownBreaker     — halts auto-trader if max drawdown breached
  ATRStopManager      — per-position ATR-scaled stop-loss and take-profit levels
  RiskEngine          — top-level facade used by auto_trader and order endpoints
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Kelly Criterion
# ──────────────────────────────────────────────────────────────────────────────

def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Full Kelly: f* = W/L - (1-W)/W_pct
    where W  = win rate, L = avg loss (positive), avg_win = avg win (positive)

    We use Half-Kelly in practice (f* / 2) to account for estimation error.
    Clipped to [0, 0.25] — never risk more than 25% of equity on one name.
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.02   # fallback: 2% fixed
    b = avg_win / avg_loss          # win/loss ratio
    f = win_rate - (1 - win_rate) / b
    half_kelly = f / 2.0
    return float(np.clip(half_kelly, 0.01, 0.25))


def kelly_shares(
    equity: float,
    price: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    signal_confidence: float = 0.5,
) -> float:
    """
    Convert Kelly fraction → number of shares.
    signal_confidence (0–1) scales the position: weak signal = smaller size.
    """
    if price <= 0 or equity <= 0:
        return 1.0
    frac = kelly_fraction(win_rate, avg_win, avg_loss)
    # Scale by signal confidence: confidence=1 → full Kelly, confidence=0.3 → 30% of Kelly
    frac *= max(0.3, signal_confidence)
    dollar_risk = equity * frac
    shares = dollar_risk / price
    return max(1.0, round(shares, 2))


# ──────────────────────────────────────────────────────────────────────────────
# Historical VaR
# ──────────────────────────────────────────────────────────────────────────────

class VaRGuard:
    """
    Historical simulation VaR at the portfolio level.
    Rejects orders that would push portfolio 1-day 95% VaR above the cap.
    """
    def __init__(self, confidence: float = 0.95, max_var_pct: float = 0.05):
        self.confidence = confidence
        self.max_var_pct = max_var_pct   # max 5% of portfolio at risk per day

    def portfolio_var(
        self,
        positions: List[dict],
        price_history: Dict[str, pd.Series],
        equity: float,
    ) -> float:
        """
        Returns current 1-day VaR as a fraction of equity.
        Uses 252-day historical returns for each position.
        """
        if not positions or equity <= 0:
            return 0.0

        portfolio_returns = []
        for pos in positions:
            sym = pos["symbol"]
            qty = pos.get("qty", 0)
            if qty <= 0 or sym not in price_history:
                continue
            px_series = price_history[sym].dropna()
            if len(px_series) < 20:
                continue
            daily_ret = px_series.pct_change().dropna().tail(252).values
            position_value = qty * pos.get("market_price", 0)
            weight = position_value / equity
            portfolio_returns.append(daily_ret * weight)

        if not portfolio_returns:
            return 0.0

        min_len = min(len(r) for r in portfolio_returns)
        combined = np.sum([r[-min_len:] for r in portfolio_returns], axis=0)
        var = float(np.percentile(combined, (1 - self.confidence) * 100))
        return abs(var)   # positive number representing loss

    def check(
        self,
        positions: List[dict],
        price_history: Dict[str, pd.Series],
        equity: float,
    ) -> Tuple[bool, float]:
        """
        Returns (allowed, current_var_pct).
        allowed=False means portfolio is already at VaR limit.
        """
        var = self.portfolio_var(positions, price_history, equity)
        allowed = var < self.max_var_pct
        return allowed, var


# ──────────────────────────────────────────────────────────────────────────────
# Drawdown Circuit Breaker
# ──────────────────────────────────────────────────────────────────────────────

class DrawdownBreaker:
    """
    Halts all new entries if peak-to-trough drawdown exceeds threshold.
    Auto-resets when equity recovers above the reset threshold.
    """
    def __init__(self, max_drawdown: float = 0.10, reset_recovery: float = 0.05):
        self.max_drawdown = max_drawdown       # halt at -10% from peak
        self.reset_recovery = reset_recovery   # resume when +5% recovered
        self._peak_equity: float = 0.0
        self._halted: bool = False
        self._halt_ts: Optional[datetime] = None

    def update(self, equity: float) -> None:
        if equity > self._peak_equity:
            self._peak_equity = equity
            if self._halted:
                recovery = (equity - self._halt_equity) / (self._halt_equity + 1e-9)
                if recovery >= self.reset_recovery:
                    self._halted = False
                    print(f"✅ Drawdown breaker reset — equity recovered to ${equity:,.2f}")

        if self._peak_equity > 0:
            dd = (equity - self._peak_equity) / self._peak_equity
            if dd <= -self.max_drawdown and not self._halted:
                self._halted = True
                self._halt_equity = equity
                self._halt_ts = datetime.now(timezone.utc)
                print(f"🛑 DRAWDOWN BREAKER TRIGGERED — drawdown={dd:.1%}, equity=${equity:,.2f}")

    @property
    def halted(self) -> bool:
        return self._halted

    def status(self) -> dict:
        dd = 0.0
        if self._peak_equity > 0:
            dd = (self._peak_equity - self._peak_equity) / self._peak_equity
        return {
            "halted": self._halted,
            "peak_equity": self._peak_equity,
            "max_drawdown_threshold": self.max_drawdown,
            "halt_timestamp": self._halt_ts.isoformat() if self._halt_ts else None,
        }


# ──────────────────────────────────────────────────────────────────────────────
# ATR-Scaled Stop/TP Manager
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class StopLevel:
    symbol: str
    entry_price: float
    stop_price: float       # ATR-scaled stop loss
    tp_price: float         # ATR-scaled take profit
    atr_at_entry: float
    side: str               # "long" | "short"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ATRStopManager:
    """
    Sets stop-loss and take-profit levels based on ATR at entry.

    Stop loss:   entry - (ATR_MULTIPLIER_STOP  × ATR)   for longs
    Take profit: entry + (ATR_MULTIPLIER_TP    × ATR)   for longs

    Using ATR instead of fixed % means stops breathe with volatility:
    - In low-vol regimes: tight stops, more trades
    - In high-vol regimes: wide stops, fewer but larger moves needed
    """
    def __init__(self, atr_stop_mult: float = 1.5, atr_tp_mult: float = 3.0):
        self.atr_stop_mult = atr_stop_mult   # 1.5× ATR stop
        self.atr_tp_mult   = atr_tp_mult     # 3.0× ATR TP → 2:1 R/R minimum
        self._stops: Dict[str, StopLevel] = {}

    def register(self, symbol: str, entry_price: float, atr: float, side: str = "long") -> StopLevel:
        if side == "long":
            stop = entry_price - self.atr_stop_mult * atr
            tp   = entry_price + self.atr_tp_mult   * atr
        else:
            stop = entry_price + self.atr_stop_mult * atr
            tp   = entry_price - self.atr_tp_mult   * atr

        level = StopLevel(
            symbol=symbol,
            entry_price=entry_price,
            stop_price=stop,
            tp_price=tp,
            atr_at_entry=atr,
            side=side,
        )
        self._stops[symbol] = level
        print(f"📍 {symbol} stop registered: entry={entry_price:.2f} stop={stop:.2f} TP={tp:.2f} (ATR={atr:.2f})")
        return level

    def check(self, symbol: str, current_price: float) -> Optional[str]:
        """
        Returns "stop" | "tp" | None.
        Call this every tick/bar for each open position.
        """
        level = self._stops.get(symbol)
        if not level:
            return None

        if level.side == "long":
            if current_price <= level.stop_price:
                return "stop"
            if current_price >= level.tp_price:
                return "tp"
        else:
            if current_price >= level.stop_price:
                return "stop"
            if current_price <= level.tp_price:
                return "tp"
        return None

    def remove(self, symbol: str) -> None:
        self._stops.pop(symbol, None)

    def all_levels(self) -> List[dict]:
        return [
            {
                "symbol":       s.symbol,
                "entry_price":  s.entry_price,
                "stop_price":   round(s.stop_price, 2),
                "tp_price":     round(s.tp_price, 2),
                "atr_at_entry": round(s.atr_at_entry, 2),
                "side":         s.side,
            }
            for s in self._stops.values()
        ]


# ──────────────────────────────────────────────────────────────────────────────
# Top-level Risk Engine facade
# ──────────────────────────────────────────────────────────────────────────────

class RiskEngine:
    """
    Single entry point for all risk decisions.
    Used by auto_trader and the /paper/order endpoint.
    """
    INITIAL_EQUITY = 100_000.0   # paper account starting equity

    def __init__(self):
        self.var_guard       = VaRGuard(confidence=0.95, max_var_pct=0.05)
        self.dd_breaker      = DrawdownBreaker(max_drawdown=0.10)
        self.stop_manager    = ATRStopManager(atr_stop_mult=1.5, atr_tp_mult=3.0)
        self._equity         = self.INITIAL_EQUITY

    def update_equity(self, positions: List[dict], realized_pnl: float = 0.0) -> float:
        """Recompute equity = cash + open positions market value + realized PnL."""
        open_value = sum(p.get("market_value", 0) for p in positions)
        self._equity = self.INITIAL_EQUITY + realized_pnl + open_value
        self.dd_breaker.update(self._equity)
        return self._equity

    def size_order(
        self,
        symbol: str,
        price: float,
        signal_score: float,
        analytics: dict,
    ) -> float:
        """
        Kelly-based position sizing from historical analytics.
        Falls back to confidence-scaled fixed size if no trade history.
        """
        total = analytics.get("total_trades", 0)
        if total >= 10:
            win_rate = analytics.get("win_rate", 50.0) / 100.0
            avg_win  = abs(analytics.get("best_trade",  50.0))
            avg_loss = abs(analytics.get("worst_trade", 50.0))
            confidence = min(1.0, abs(signal_score) / 0.5)
            shares = kelly_shares(
                self._equity, price, win_rate, avg_win, avg_loss, confidence
            )
        else:
            # Not enough history — use small fixed size scaled by confidence
            confidence = min(1.0, abs(signal_score) / 0.5)
            shares = max(1.0, round(confidence * 3, 0))

        return shares

    def pre_trade_check(
        self,
        symbol: str,
        side: str,
        shares: float,
        price: float,
        positions: List[dict],
    ) -> Tuple[bool, str]:
        """
        Returns (approved, reason).
        Gates every order through drawdown breaker + position concentration.
        """
        if self.dd_breaker.halted:
            return False, "drawdown_breaker_active"

        # Max single-position concentration: 20% of equity
        order_value = shares * price
        if self._equity > 0 and (order_value / self._equity) > 0.20:
            shares_allowed = int((self._equity * 0.20) / price)
            return False, f"concentration_limit: max {shares_allowed} shares at this price"

        # Max total open positions: 8 symbols
        open_syms = {p["symbol"] for p in positions if p.get("qty", 0) > 0}
        if side == "buy" and symbol not in open_syms and len(open_syms) >= 8:
            return False, "max_positions_reached"

        return True, "approved"

    def register_entry(self, symbol: str, price: float, atr: float, side: str = "long"):
        """Register ATR stops after a fill."""
        self.stop_manager.register(symbol, price, atr, side)

    def check_exits(self, symbol: str, current_price: float) -> Optional[str]:
        """Check if stop/TP triggered. Returns 'stop' | 'tp' | None."""
        return self.stop_manager.check(symbol, current_price)

    def on_exit(self, symbol: str):
        """Clean up stop levels after a position is closed."""
        self.stop_manager.remove(symbol)

    def status(self) -> dict:
        return {
            "equity":          round(self._equity, 2),
            "drawdown_breaker": self.dd_breaker.status(),
            "open_stops":       self.stop_manager.all_levels(),
        }


# Singleton shared across the app
risk = RiskEngine()
