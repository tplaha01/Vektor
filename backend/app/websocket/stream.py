from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Dict

from fastapi import WebSocket

from app.config import get_settings
from app.data.market_data import FEED


WATCHLIST = ["AAPL", "MSFT", "NVDA", "SPY", "TSLA", "AMZN", "GOOGL", "META"]
logger = logging.getLogger("alfred.websocket.stream")


class StreamManager:
    def __init__(self):
        self._lock = RLock()
        self.active: set[WebSocket] = set()
        self._tick_cache: Dict[str, dict] = {}
        self._pending_symbols: set[str] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tick_event: asyncio.Event | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
        with self._lock:
            snapshot = list(self._tick_cache.values())
        if snapshot:
            try:
                await ws.send_json({"type": "tick_batch", "data": snapshot})
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

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        if self._tick_event is None:
            self._tick_event = asyncio.Event()

    @property
    def tick_event(self) -> asyncio.Event | None:
        return self._tick_event

    def update_tick(self, symbol: str, price: float, prev_close: float | None = None) -> dict[str, object]:
        with self._lock:
            existing = self._tick_cache.get(symbol, {})
            ref = prev_close or existing.get("prev_close") or price
        change = price - ref
        change_pct = (change / ref * 100) if ref else 0.0
        row = {
            "symbol": symbol,
            "price": price,
            "prev_close": ref,
            "change": round(change, 4),
            "change_pct": round(change_pct, 4),
            "ts": _utc_iso(),
        }
        with self._lock:
            self._tick_cache[symbol] = row
        return row

    def queue_tick(self, symbol: str, price: float, prev_close: float | None = None) -> None:
        self.update_tick(symbol, price, prev_close)
        with self._lock:
            self._pending_symbols.add(symbol)
        if self._loop is None or self._tick_event is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._tick_event.set)
        except RuntimeError:
            pass

    def drain_pending_ticks(self) -> list[dict[str, object]]:
        with self._lock:
            if not self._pending_symbols:
                return []
            symbols = list(self._pending_symbols)
            self._pending_symbols.clear()
            return [dict(self._tick_cache[symbol]) for symbol in symbols if symbol in self._tick_cache]


manager = StreamManager()

# Previous-close cache populated at startup
_prev_close: Dict[str, float] = {}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _alpaca_tick_callback(symbol: str, price: float):
    manager.queue_tick(symbol, price, _prev_close.get(symbol))


def _fetch_prev_closes() -> None:
    """Pull yesterday's close for each watchlist symbol at startup."""
    for sym in WATCHLIST:
        try:
            hist = FEED.history(sym, bars=5)
            if hist is not None and len(hist) >= 2:
                _prev_close[sym] = float(hist["close"].iloc[-2])
        except Exception:
            pass
    logger.info("Previous closes loaded for %s symbols", len(_prev_close))


def _collect_tick_and_positions(symbols: list[str]) -> tuple[list[dict], list]:
    """
    Blocking market data + positions collection, intended to run off-thread.
    """
    tick_data: list[dict] = []
    for sym in symbols:
        px = FEED.price(sym)
        if px and px > 0:
            manager.update_tick(sym, px, _prev_close.get(sym))
            tick_data.append(manager._tick_cache[sym])

    from app.core.context import broker

    positions = broker.list_positions(lambda s: FEED.price(s))
    return tick_data, positions


def _collect_positions() -> list:
    from app.core.context import broker

    return broker.list_positions(lambda s: FEED.price(s))


async def stream_loop():
    settings = get_settings()

    # Fetch prev closes first so change is meaningful from the first tick.
    _fetch_prev_closes()
    manager.set_event_loop(asyncio.get_running_loop())

    FEED.subscribe(_alpaca_tick_callback)
    if settings.ALPACA_STREAM_ENABLED:
        FEED.start_stream(WATCHLIST)
    else:
        logger.info("Alpaca stream disabled; using REST/cached prices only.")

    broadcast_interval = max(0.1, float(settings.WEBSOCKET_BROADCAST_INTERVAL))
    logger.info("Stream loop started; broadcast_interval=%ss", broadcast_interval)
    last_positions_refresh = 0.0

    while True:
        tick_event = manager.tick_event
        woke_on_tick = False
        if tick_event is None:
            await asyncio.sleep(broadcast_interval)
        else:
            try:
                await asyncio.wait_for(tick_event.wait(), timeout=broadcast_interval)
                woke_on_tick = True
            except asyncio.TimeoutError:
                woke_on_tick = False
            finally:
                tick_event.clear()

        if not manager.active:
            manager.drain_pending_ticks()
            continue

        try:
            timeout_seconds = max(0.2, float(settings.WEBSOCKET_STREAM_FETCH_TIMEOUT_SECONDS))
            if woke_on_tick:
                tick_data = manager.drain_pending_ticks()
                if tick_data:
                    await manager.broadcast(
                        {
                            "type": "tick_batch",
                            "data": tick_data,
                            "ts": _utc_iso(),
                        }
                    )
                if (monotonic() - last_positions_refresh) >= broadcast_interval:
                    positions = await asyncio.wait_for(
                        asyncio.to_thread(_collect_positions),
                        timeout=timeout_seconds,
                    )
                    if positions:
                        await manager.broadcast(
                            {
                                "type": "positions_update",
                                "data": positions,
                                "ts": _utc_iso(),
                            }
                        )
                    last_positions_refresh = monotonic()
                continue

            tick_data, positions = await asyncio.wait_for(
                asyncio.to_thread(_collect_tick_and_positions, WATCHLIST),
                timeout=timeout_seconds,
            )
            if tick_data:
                await manager.broadcast(
                    {
                        "type": "tick_batch",
                        "data": tick_data,
                        "ts": _utc_iso(),
                    }
                )
            if positions:
                await manager.broadcast(
                    {
                        "type": "positions_update",
                        "data": positions,
                        "ts": _utc_iso(),
                    }
                )
                last_positions_refresh = monotonic()

        except asyncio.TimeoutError:
            logger.warning("Stream loop fetch timeout; skipping cycle")
        except Exception as exc:
            logger.warning("Stream loop error: %s", exc)
