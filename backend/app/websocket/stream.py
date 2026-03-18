from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Dict

from fastapi import WebSocket
from app.config import get_settings
from app.data.market_data import FEED


WATCHLIST = ["AAPL", "MSFT", "NVDA", "SPY", "TSLA", "AMZN", "GOOGL", "META"]


class StreamManager:
    def __init__(self):
        self.active: set[WebSocket] = set()
        self._tick_cache: Dict[str, dict] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
        if self._tick_cache:
            try:
                await ws.send_json({"type": "tick_batch", "data": list(self._tick_cache.values())})
            except Exception:
                pass

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: dict):
        if not self.active:
            return
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for d in dead:
            self.disconnect(d)

    def update_tick(self, symbol: str, price: float, prev_close: float | None = None):
        existing = self._tick_cache.get(symbol, {})
        ref = prev_close or existing.get("prev_close") or price
        change = price - ref
        change_pct = (change / ref * 100) if ref else 0.0
        self._tick_cache[symbol] = {
            "symbol":     symbol,
            "price":      price,
            "prev_close": ref,
            "change":     round(change, 4),
            "change_pct": round(change_pct, 4),
            "ts":         datetime.utcnow().isoformat(),
        }


manager = StreamManager()

# Previous-close cache populated at startup
_prev_close: Dict[str, float] = {}


def _alpaca_tick_callback(symbol: str, price: float):
    manager.update_tick(symbol, price, _prev_close.get(symbol))


def _fetch_prev_closes() -> None:
    """Pull yesterday's close for each watchlist symbol at startup."""
    for sym in WATCHLIST:
        try:
            hist = FEED.history(sym, bars=5)
            if hist is not None and len(hist) >= 2:
                _prev_close[sym] = float(hist["close"].iloc[-2])
        except Exception:
            pass
    print(f"📊 Previous closes loaded: {_prev_close}")


async def stream_loop():
    settings = get_settings()

    # Fetch prev closes first so change is meaningful from the first tick
    _fetch_prev_closes()

    FEED.subscribe(_alpaca_tick_callback)
    FEED.start_stream(WATCHLIST)

    print(f"📡 Stream loop started — broadcasting every {settings.WEBSOCKET_BROADCAST_INTERVAL}s")

    while True:
        await asyncio.sleep(settings.WEBSOCKET_BROADCAST_INTERVAL)

        if not manager.active:
            continue

        try:
            tick_data = []
            for sym in WATCHLIST:
                px = FEED.price(sym)
                if px and px > 0:
                    manager.update_tick(sym, px, _prev_close.get(sym))
                    tick_data.append(manager._tick_cache[sym])

            if tick_data:
                await manager.broadcast({
                    "type": "tick_batch",
                    "data": tick_data,
                    "ts":   datetime.utcnow().isoformat(),
                })

            from app.core.context import broker
            positions = broker.list_positions(lambda s: FEED.price(s))
            if positions:
                await manager.broadcast({
                    "type": "positions_update",
                    "data": positions,
                    "ts":   datetime.utcnow().isoformat(),
                })

        except Exception as e:
            print(f"⚠️ Stream loop error: {e}")
