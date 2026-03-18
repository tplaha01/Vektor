from __future__ import annotations
"""
Vectorised Backtesting Engine — Hybrid-consistent

Fixes:
  1) Threshold defaults match live Settings (0.20 / -0.20)
  2) Signals incorporate ML alpha + technical, weight-renormalised
  3) Volatility filter matches live logic (ATR/price > VOL_CAP => HOLD)
  4) ATR uses Wilder method via ta.volatility.AverageTrueRange
  5) ML schema drift protected via alpha_model reindex fix
"""

import numpy as np
import pandas as pd
import yfinance as yf
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from ta.volatility import AverageTrueRange
from app.indicators.technical import technical_score
from app.config import get_settings


@dataclass
class BacktestConfig:
    initial_equity: float = 100_000.0
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    buy_threshold: float = 0.20
    sell_threshold: float = -0.20
    max_position_pct: float = 0.40
    risk_free_rate: float = 0.05
    cooldown_bars: int = 3


@dataclass
class Trade:
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    hold_days: int
    regime: str


@dataclass
class BacktestResult:
    symbol: str
    period: str
    config: BacktestConfig
    equity_curve: pd.Series
    benchmark_curve: pd.Series
    trades: List[Trade]
    metrics: Dict[str, Any]
    signal_series: pd.Series
    bars: pd.DataFrame


def _fetch(symbol: str, period: str) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval="1d")
    if df.empty:
        raise ValueError(f"No data returned for {symbol}")
    df = df.reset_index()
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.rename(columns={"Date": "date", "Open": "open", "High": "high",
                            "Low": "low", "Close": "close", "Volume": "volume"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.reset_index(drop=True)


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    ind = AverageTrueRange(
        high=df["high"].astype(float),
        low=df["low"].astype(float),
        close=df["close"].astype(float),
        window=period,
        fillna=False,
    )
    return ind.average_true_range()


def _compute_signals_hybrid_like(df: pd.DataFrame, min_bars: int = 60) -> tuple[pd.Series, pd.Series]:

    settings = get_settings()

    # Backtest-optimized weights
    wT = 0.20
    wM = 0.50

    ATR_N = settings.ATR_PERIOD
    VOL_CAP = settings.VOL_THRESHOLD

    atr_series = _compute_atr(df, ATR_N)

    signals = pd.Series(np.nan, index=df.index, dtype=float)
    regimes = pd.Series("", index=df.index, dtype=object)

    try:
        from app.ml.alpha_model import predict, ensure_model, model_status
        ensure_model()
        ml_ok = bool(model_status().get("ready"))
    except Exception:
        predict = None
        ml_ok = False

    print("ML OK:", ml_ok)

    for i in range(min_bars, len(df)):
        try:
            window = df.iloc[:i + 1].copy()

            # Technical
            dbg = technical_score(window, debug=True)
            tech = dbg["score"] if isinstance(dbg, dict) else float(dbg)
            regimes.iloc[i] = dbg.get("regime", "") if isinstance(dbg, dict) else ""

            # ML alpha
            ml = 0.0
            if ml_ok and predict is not None:
                ml = float(
                    predict(window.rename(columns={"date": "ts"})
                            if "date" in window.columns else window)
                )

            # Volatility filter
            atr_val = float(atr_series.iloc[i])
            px = float(window["close"].iloc[-1])
            vol_ratio = (atr_val / px) if px else 0.0

            if np.isfinite(vol_ratio) and vol_ratio > VOL_CAP:
                signals.iloc[i] = 0.0
                continue

            # Proper normalization
            if ml_ok:
                active_w = wT + wM
                score = (wT * tech + wM * ml) / active_w if active_w > 0 else 0.0
            else:
                score = tech

            signals.iloc[i] = float(np.clip(score, -1.0, 1.0))

        except Exception as e:
            print("Signal error:", e)
            signals.iloc[i] = 0.0

    return signals, regimes

def _compute_metrics(equity_curve, trades, benchmark_curve, config):
    if len(equity_curve) < 2:
        return {}
    returns = equity_curve.pct_change().dropna()
    days = max((equity_curve.index[-1] - equity_curve.index[0]).days, 1)
    years = days / 365.25
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0
    bmark_return = ((benchmark_curve.iloc[-1] / benchmark_curve.iloc[0]) - 1.0
                    if len(benchmark_curve) > 1 else 0.0)
    cagr = (1 + total_return) ** (1 / max(years, 0.01)) - 1

    # Sharpe
    rf_daily = (1 + config.risk_free_rate) ** (1 / 252) - 1
    excess = returns - rf_daily
    sharpe = float(excess.mean() / (excess.std() + 1e-9) * np.sqrt(252))

    # Sortino
    neg = returns[returns < 0]
    sortino = float(returns.mean() / (neg.std() + 1e-9) * np.sqrt(252)) if len(neg) else 0.0

    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / (rolling_max + 1e-9)
    max_dd = float(drawdown.min())

    calmar = float(cagr / abs(max_dd)) if max_dd != 0 else 0.0
    ann_vol = float(returns.std() * np.sqrt(252))

    n = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]

    exits, regimes_count = {}, {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
        regimes_count[t.regime] = regimes_count.get(t.regime, 0) + 1

    return {
        "total_return_pct": round(total_return * 100, 2),
        "benchmark_return_pct": round(bmark_return * 100, 2),
        "alpha_pct": round((total_return - bmark_return) * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "ann_volatility_pct": round(ann_vol * 100, 2),
        "total_trades": n,
        "win_rate_pct": round(len(wins) / n * 100, 1) if n else 0.0,
        "avg_win": round(float(np.mean([t.pnl for t in wins])), 2) if wins else 0.0,
        "avg_loss": round(float(np.mean([t.pnl for t in losses])), 2) if losses else 0.0,
        "profit_factor": round(sum(t.pnl for t in wins) / (abs(sum(t.pnl for t in losses)) + 1e-9), 3),
        "avg_hold_days": round(float(np.mean([t.hold_days for t in trades])), 1) if trades else 0.0,
        "exit_reasons": exits,
        "regime_breakdown": regimes_count,
        "final_equity": round(float(equity_curve.iloc[-1]), 2),
        "period_days": days,
    }


def run_backtest(
    symbol: str,
    period: str = "1y",
    config: Optional[BacktestConfig] = None,
    benchmark: str = "SPY"
) -> BacktestResult:
    settings = get_settings()
    if config is None:
        config = BacktestConfig(
            buy_threshold=settings.BUY_THRESHOLD,
            sell_threshold=settings.SELL_THRESHOLD,
        )

    df = _fetch(symbol, period)
    if len(df) < 80:
        raise ValueError(f"Too few bars ({len(df)}) for {symbol} over {period}")

    try:
        bmark_df = _fetch(benchmark, period)
        bmark_norm = config.initial_equity * (bmark_df["close"] / bmark_df["close"].iloc[0])
        bmark_curve = pd.Series(bmark_norm.values, index=pd.to_datetime(bmark_df["date"]))
    except Exception:
        bmark_curve = pd.Series(dtype=float)

    # Hybrid-like signals
    signals, regimes = _compute_signals_hybrid_like(df)

    # Use ATR for stop/TP logic
    atr_series = _compute_atr(df, period=settings.ATR_PERIOD)

    buy_mult = 1.0 + config.commission_pct + config.slippage_pct
    sell_mult = 1.0 - config.commission_pct - config.slippage_pct

    cash = config.initial_equity
    shares = 0.0
    entry_cost = 0.0
    entry_date = None
    entry_regime = ""
    stop_px = 0.0
    tp_px = 0.0
    trail_high = 0.0
    cooldown_left = 0

    equity_vals: List[float] = []
    equity_dates: List[Any] = []
    trades: List[Trade] = []

    def close_position(exit_px_raw, date, reason):
        nonlocal cash, shares, entry_cost, entry_date, stop_px, tp_px, entry_regime, trail_high, cooldown_left
        proceeds_ps = exit_px_raw * sell_mult
        pnl = (proceeds_ps - entry_cost) * shares
        cash += proceeds_ps * shares
        trades.append(Trade(
            symbol=symbol.upper(),
            entry_date=str(entry_date)[:10],
            exit_date=str(date)[:10],
            entry_price=round(entry_cost, 4),
            exit_price=round(proceeds_ps, 4),
            shares=round(shares, 4),
            pnl=round(pnl, 2),
            pnl_pct=round((proceeds_ps / entry_cost - 1) * 100, 2),
            exit_reason=reason,
            hold_days=(date - entry_date).days if entry_date else 0,
            regime=entry_regime,
        ))
        if reason == "stop":
            cooldown_left = config.cooldown_bars
        shares = entry_cost = stop_px = tp_px = trail_high = 0.0
        entry_date = None
        entry_regime = ""

    for i in range(1, len(df)):
        row = df.iloc[i]
        date = row["date"]
        sig = signals.iloc[i - 1]
        regime = regimes.iloc[i - 1]
        atr_val = float(atr_series.iloc[i - 1]) if not np.isnan(atr_series.iloc[i - 1]) else 0.0

        open_px = float(row["open"])
        high_px = float(row["high"])
        low_px = float(row["low"])
        close_px = float(row["close"])

        equity = cash + shares * close_px
        equity_vals.append(equity)
        equity_dates.append(date)

        if cooldown_left > 0:
            cooldown_left -= 1

        if np.isnan(sig):
            continue

        # Regime-specific stop/TP multipliers
        if regime in ("TREND_UP", "TREND_DOWN"):
            stop_mult = 2.5
            tp_mult = 6.0
            use_trail = True
        elif regime in ("BREAKOUT_UP", "BREAKOUT_DOWN"):
            stop_mult = 1.5
            tp_mult = 4.0
            use_trail = False
        elif regime == "HIGH_VOL":
            stop_mult = 3.5
            tp_mult = 0.0
            use_trail = False
        else:
            stop_mult = 2.5
            tp_mult = 3.0
            use_trail = False

        # Trailing stop update
        if shares > 0 and use_trail and atr_val > 0:
            if high_px > trail_high:
                trail_high = high_px
            trail_stop = trail_high - stop_mult * atr_val
            if trail_stop > stop_px:
                stop_px = trail_stop

        # Stop / TP check
        if shares > 0:
            if low_px <= stop_px:
                close_position(min(open_px, stop_px), date, "stop")
                continue
            if tp_px > 0 and high_px >= tp_px:
                close_position(max(open_px, tp_px), date, "tp")
                continue

        # Entry
        if sig > config.buy_threshold and shares == 0 and cooldown_left == 0:
            strength = min(abs(sig) / 0.5, 1.0)
            alloc_pct = config.max_position_pct * (0.5 + 0.5 * strength)
            max_dollars = equity * alloc_pct
            n_shares = max(1.0, np.floor(max_dollars / (open_px * buy_mult)))
            total_cost = n_shares * open_px * buy_mult

            if total_cost <= cash:
                cash -= total_cost
                shares = n_shares
                entry_cost = open_px * buy_mult
                entry_date = date
                entry_regime = regime
                trail_high = open_px

                if atr_val > 0:
                    stop_px = entry_cost - stop_mult * atr_val
                    tp_px = (entry_cost + tp_mult * atr_val) if tp_mult > 0 else 0.0
                else:
                    stop_px = entry_cost * 0.97
                    tp_px = entry_cost * 1.10

        elif sig < config.sell_threshold and shares > 0:
            close_position(open_px, date, "signal")

    if shares > 0:
        last = df.iloc[-1]
        close_position(float(last["close"]), last["date"], "end_of_data")

    equity_curve = pd.Series(equity_vals, index=pd.to_datetime(equity_dates), name="equity")
    metrics = _compute_metrics(equity_curve, trades, bmark_curve, config)

    return BacktestResult(
        symbol=symbol.upper(),
        period=period,
        config=config,
        equity_curve=equity_curve,
        benchmark_curve=bmark_curve,
        trades=trades,
        metrics=metrics,
        signal_series=signals,
        bars=df,
    )


def result_to_dict(r: BacktestResult) -> dict:
    return {
        "symbol": r.symbol,
        "period": r.period,
        "metrics": r.metrics,
        "equity_curve": [{"date": str(d)[:10], "equity": round(v, 2)} for d, v in r.equity_curve.items()],
        "benchmark_curve": [{"date": str(d)[:10], "equity": round(v, 2)} for d, v in r.benchmark_curve.items()]
        if len(r.benchmark_curve) > 0 else [],
        "trades": [{
            "symbol": t.symbol,
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "shares": t.shares,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "exit_reason": t.exit_reason,
            "hold_days": t.hold_days,
            "regime": t.regime
        } for t in r.trades],
        "signal_series": [
            {"date": str(r.bars.iloc[i]["date"])[:10], "signal": round(float(sig), 4)}
            for i, sig in enumerate(r.signal_series) if not np.isnan(sig)
        ],
    }