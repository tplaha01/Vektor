from __future__ import annotations

"""
Auto-trader
===========
Scans the watchlist every TRADE_INTERVAL seconds.
Every decision passes through the RiskEngine before execution.
"""

import asyncio
from datetime import datetime

from app.analytics import build_metrics_from_broker
from app.config import get_settings
from app.core.context import broker
from app.data.market_data import FEED
from app.fund.runtime_guard import data_integrity_guard
from app.risk.engine import risk
from app.strategies.hybrid import hybrid_signal
from app.websocket.stream import manager

settings = get_settings()

WATCHLIST = ["AAPL", "MSFT", "NVDA", "SPY", "TSLA", "AMZN", "GOOGL", "META"]
TRADE_INTERVAL = 30  # seconds between full scans


def _current_atr(symbol: str) -> float:
    """Fetch ATR for stop registration after entry."""
    try:
        hist = FEED.history(symbol, bars=30)
        if hist is None or len(hist) < 15:
            return 0.0
        high = hist["high"].astype(float)
        low = hist["low"].astype(float)
        close = hist["close"].astype(float)
        hl = high - low
        hc = (high - close.shift()).abs()
        lc = (low - close.shift()).abs()
        import pandas as pd

        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        return float(tr.rolling(14).mean().iloc[-1])
    except Exception:
        return 0.0


async def auto_trading_loop():
    """
    Main trading loop. Runs as a FastAPI background task.
    Flow per symbol:
      1. Generate hybrid signal
      2. Check risk engine pre-trade gates
      3. Kelly-size the order
      4. Submit via broker
      5. Register ATR stops
      6. Manage existing stops/TPs
    """
    print(f"Auto-trader started - scanning every {TRADE_INTERVAL}s")

    while True:
        if data_integrity_guard.halted():
            print(f"Auto-trader paused: {data_integrity_guard.halt_reason() or 'system_halted'}")
            await asyncio.sleep(max(TRADE_INTERVAL, 60))
            continue

        print(f"\n{'-' * 50}")
        print(f"{datetime.utcnow().strftime('%H:%M:%S UTC')} | equity=${risk._equity:,.0f}")

        positions = broker.list_positions(lambda s: FEED.price(s))
        analytics = build_metrics_from_broker(broker)

        # Update equity and drawdown breaker.
        realized_pnl = analytics.get("realized_pnl", 0.0)
        risk.update_equity(positions, realized_pnl)

        if risk.dd_breaker.halted:
            print("Drawdown breaker active - no new entries this cycle")
        else:
            for sym in WATCHLIST:
                try:
                    sig = hybrid_signal(sym)
                    action = sig["action"]
                    score = sig["score"]
                    price = FEED.price(sym)

                    if price <= 0:
                        continue

                    tag = f"{sym:5s} | score={score:+.3f} | vol={sig.get('volatility') or 0:.2%} | {action.upper()}"

                    if action == "buy":
                        already_held = any(p["symbol"] == sym and p["qty"] > 0 for p in positions)
                        if already_held:
                            print(f"SKIP  {tag} (already holding)")
                        else:
                            qty = risk.size_order(sym, price, score, analytics)
                            approved, reason = risk.pre_trade_check(sym, "buy", qty, price, positions)
                            if approved:
                                broker.submit_order(sym, "buy", qty, price)
                                atr_val = _current_atr(sym)
                                if atr_val > 0:
                                    risk.register_entry(sym, price, atr_val, "long")
                                print(f"BUY   {tag} | qty={qty}")
                            else:
                                print(f"BLOCK {tag} [{reason}]")

                    elif action == "sell":
                        held = next((p for p in positions if p["symbol"] == sym and p["qty"] > 0), None)
                        if held:
                            qty = held["qty"]
                            broker.submit_order(sym, "sell", qty, price)
                            risk.on_exit(sym)
                            print(f"SELL  {tag} | qty={qty}")
                        else:
                            print(f"HOLD  {tag} (no position to sell)")
                    else:
                        print(f"HOLD  {tag}")

                except Exception as exc:
                    print(f"Error processing {sym}: {exc}")

        # Stop-loss / take-profit scan.
        positions = broker.list_positions(lambda s: FEED.price(s))
        for pos in positions:
            sym = pos["symbol"]
            qty = pos.get("qty", 0)
            px = pos.get("market_price", 0)
            if qty <= 0 or px <= 0:
                continue

            exit_signal = risk.check_exits(sym, px)
            if exit_signal == "stop":
                broker.submit_order(sym, "sell", qty, px)
                risk.on_exit(sym)
                pct = (px - pos["avg_price"]) / pos["avg_price"]
                print(f"STOP {sym} @ {px:.2f} ({pct:+.1%})")
            elif exit_signal == "tp":
                broker.submit_order(sym, "sell", qty, px)
                risk.on_exit(sym)
                pct = (px - pos["avg_price"]) / pos["avg_price"]
                print(f"TAKE PROFIT {sym} @ {px:.2f} ({pct:+.1%})")

        fresh = broker.list_positions(lambda s: FEED.price(s))
        await manager.broadcast(
            {
                "type": "positions_update",
                "data": fresh,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        await manager.broadcast(
            {
                "type": "risk_update",
                "data": risk.status(),
                "ts": datetime.utcnow().isoformat(),
            }
        )

        await asyncio.sleep(TRADE_INTERVAL)

