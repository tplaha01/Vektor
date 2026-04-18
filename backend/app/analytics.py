from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime, timezone
import math

@dataclass
class Fill:
    ts: datetime
    symbol: str
    side: str   # "buy" | "sell"
    qty: float
    price: float

@dataclass
class RoundTrip:
    symbol: str
    open_ts: datetime
    close_ts: datetime
    qty: float
    avg_buy: float
    avg_sell: float
    pnl: float


def _coerce_ts(value: Any) -> datetime:
    """Normalize timestamps to timezone-aware UTC datetimes."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)
    else:
        return datetime.now(timezone.utc)

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _fifo_round_trips(fills: List[Fill]) -> List[RoundTrip]:
    """Pair buys and sells FIFO per symbol to produce round trips (realized trades)."""
    by_sym: Dict[str, List[Fill]] = {}
    for f in fills:
        by_sym.setdefault(f.symbol, []).append(f)

    trips: List[RoundTrip] = []

    for sym, fs in by_sym.items():
        fs = sorted(fs, key=lambda x: x.ts)
        buys: List[Fill] = []   # open lots
        sells: List[Fill] = []  # used only for averaging on close

        for f in fs:
            if f.side == "buy":
                buys.append(Fill(f.ts, sym, f.side, f.qty, f.price))
            else:  # sell closes buys FIFO
                sell_rem = f.qty
                close_px = f.price
                close_ts = f.ts
                sells.append(f)

                while sell_rem > 1e-9 and buys:
                    b = buys[0]
                    take = min(b.qty, sell_rem)
                    # realize portion
                    pnl = (close_px - b.price) * take
                    trips.append(RoundTrip(
                        symbol=sym,
                        open_ts=b.ts,
                        close_ts=close_ts,
                        qty=take,
                        avg_buy=b.price,
                        avg_sell=close_px,
                        pnl=pnl
                    ))
                    b.qty -= take
                    sell_rem -= take
                    if b.qty <= 1e-9:
                        buys.pop(0)
                # if sell > open qty, excess ignored (shorts not modeled here)

    return trips

def metrics_from_round_trips(trips: List[RoundTrip]) -> Dict[str, Any]:
    total = len(trips)
    wins = sum(1 for t in trips if t.pnl > 0)
    losses = sum(1 for t in trips if t.pnl < 0)
    realized = sum(t.pnl for t in trips)
    avg_pnl = realized / total if total else 0.0
    best = max((t.pnl for t in trips), default=0.0)
    worst = min((t.pnl for t in trips), default=0.0)

    # simple equity curve for max drawdown
    eq = 0.0
    peak = 0.0
    mdd = 0.0
    for t in sorted(trips, key=lambda x: x.close_ts):
        eq += t.pnl
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)

    return {
        "total_trades": total,
        "closed_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / total * 100.0) if total else 0.0,
        "realized_pnl": realized,
        "avg_pnl": avg_pnl,
        "best_trade": best,
        "worst_trade": worst,
        "max_drawdown": mdd,  # negative number
    }

def build_metrics_from_broker(broker) -> Dict[str, Any]:
    """
    Expect broker.order_history as a list of dicts with:
    {symbol, side, qty, avg_price or price, created_at}
    """
    fills: List[Fill] = []
    for o in broker.order_history:  # adjust to your broker attribute
        ts = _coerce_ts(o.get("created_at"))
        fills.append(Fill(
            ts=ts,
            symbol=o["symbol"],
            side=o["side"],
            qty=float(o["qty"]),
            price=float(o.get("avg_price", o.get("price", 0.0)))
        ))
    trips = _fifo_round_trips(fills)
    m = metrics_from_round_trips(trips)
    # also return last 10 trades for table
    last_trades = sorted(trips, key=lambda x: x.close_ts)[-10:]
    m["recent_trades"] = [
        {
            "symbol": t.symbol,
            "qty": t.qty,
            "open_ts": t.open_ts.isoformat(),
            "close_ts": t.close_ts.isoformat(),
            "buy": t.avg_buy,
            "sell": t.avg_sell,
            "pnl": t.pnl,
        }
        for t in reversed(last_trades)
    ]
    return m
