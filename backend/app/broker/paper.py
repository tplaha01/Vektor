from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict


@dataclass
class PaperOrder:
    id: str
    symbol: str
    side: str
    qty: float
    avg_price: float
    created_at: datetime
    status: str = "filled"


# Realistic fill simulation
_SLIPPAGE_BPS = 5  # 0.05% adverse slippage per trade
_COMMISSION_PCT = 0.001  # 0.1% commission
_log = logging.getLogger("alfred.broker.paper")


def _fill_price(side: str, price: float) -> float:
    """Buys fill slightly above mid, sells slightly below. Adds small random noise."""
    slip = price * (_SLIPPAGE_BPS / 10_000)
    noise = price * random.uniform(0, _SLIPPAGE_BPS / 20_000)
    if side == "buy":
        return round(price + slip + noise, 4)
    return round(price - slip - noise, 4)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaperBroker:

    def __init__(self):
        self.cash: float = 100_000.0
        self.positions: Dict[str, Dict] = {}
        self.order_history: list = []
        self._order_counter: int = 0
        self._db_ready: bool = False

    # Persistence

    def restore_from_db(self) -> None:
        """Load state from SQLite on startup. Call after init_db()."""
        try:
            from app.storage.db import load_orders, load_positions, load_latest_cash

            self.positions = load_positions()
            self.order_history = load_orders()
            self.cash = load_latest_cash(default=100_000.0)
            self._order_counter = len(self.order_history)
            self._db_ready = True
            _log.info(
                "broker restored cash=%s positions=%s orders=%s",
                f"${self.cash:,.2f}",
                list(self.positions.keys()),
                len(self.order_history),
            )
        except Exception as exc:
            _log.warning("broker restore failed (%s); starting fresh", exc)

    def _persist(self, order_dict: dict) -> None:
        if not self._db_ready:
            return
        try:
            from app.storage.db import save_order, save_positions, save_cash

            save_order(order_dict)
            save_positions(self.positions)
            save_cash(self.cash)
        except Exception as exc:
            _log.warning("db persist error: %s", exc)

    # Submit Order

    def submit_order(self, symbol: str, side: str, qty: float, price: float) -> PaperOrder:
        symbol = symbol.upper()
        qty = float(qty)
        price = float(price)
        filled_price = _fill_price(side, price)
        commission = filled_price * qty * _COMMISSION_PCT

        if side == "buy":
            cost = qty * filled_price + commission
            if cost > self.cash:
                raise ValueError(f"Insufficient cash: need ${cost:.2f}, have ${self.cash:.2f}")
            self.cash -= cost
            pos = self.positions.get(symbol)
            if pos:
                total_qty = pos["qty"] + qty
                pos["avg_price"] = ((pos["avg_price"] * pos["qty"]) + (filled_price * qty)) / total_qty
                pos["qty"] = total_qty
            else:
                self.positions[symbol] = {"symbol": symbol, "qty": qty, "avg_price": filled_price}

        elif side == "sell":
            pos = self.positions.get(symbol)
            if not pos or pos["qty"] < qty:
                raise ValueError(f"Insufficient shares: have {pos['qty'] if pos else 0}, need {qty}")
            self.cash += qty * filled_price - commission
            pos["qty"] -= qty
            if pos["qty"] <= 1e-9:
                del self.positions[symbol]

        self._order_counter += 1
        now = _utc_now().isoformat().replace("+00:00", "Z")
        order_dict = {
            "id": str(self._order_counter),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "avg_price": filled_price,
            "price": filled_price,
            "status": "filled",
            "created_at": now,
        }
        self.order_history.append(order_dict)
        self._persist(order_dict)

        return PaperOrder(
            id=str(self._order_counter),
            symbol=symbol,
            side=side,
            qty=qty,
            avg_price=filled_price,
            created_at=_utc_now(),
        )

    # Queries

    def list_positions(self, price_lookup: Callable[[str], float]) -> list:
        results = []
        for symbol, pos in self.positions.items():
            qty = float(pos["qty"])
            avg_price = float(pos["avg_price"])
            market_price = float(price_lookup(symbol))
            results.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "avg_price": round(avg_price, 4),
                    "market_price": round(market_price, 4),
                    "market_value": round(qty * market_price, 2),
                    "unrealized_pnl": round((market_price - avg_price) * qty, 2),
                }
            )
        return results

    def list_orders(self) -> list:
        return list(reversed(self.order_history))

    # Compatibility helpers for monitoring/legacy code paths

    def get_cash(self) -> float:
        return float(self.cash)

    def get_portfolio_value(self, price_lookup: Callable[[str], float]) -> float:
        positions_value = 0.0
        for symbol, pos in self.positions.items():
            qty = float(pos.get("qty", 0.0))
            positions_value += qty * float(price_lookup(symbol))
        return float(self.cash + positions_value)

    def list_symbols(self) -> list[str]:
        return sorted(self.positions.keys())

    # Admin controls

    def persist_state(self) -> None:
        """
        Persist current broker cash/positions snapshot without creating a new order.
        """
        if not self._db_ready:
            return
        try:
            from app.storage.db import save_positions, save_cash

            save_positions(self.positions)
            save_cash(self.cash)
        except Exception as exc:
            _log.warning("db state persist error: %s", exc)
