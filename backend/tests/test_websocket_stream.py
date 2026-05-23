import asyncio
from contextlib import suppress

from app.websocket import stream as ws_stream


class _Settings:
    ALPACA_STREAM_ENABLED = True
    WEBSOCKET_BROADCAST_INTERVAL = 0.25
    WEBSOCKET_STREAM_FETCH_TIMEOUT_SECONDS = 0.25


def _reset_stream_state() -> None:
    ws_stream.manager.active.clear()
    ws_stream.manager._tick_cache.clear()
    ws_stream.manager._pending_symbols.clear()
    ws_stream.manager._loop = None
    ws_stream.manager._tick_event = None
    ws_stream._prev_close.clear()


def _wait_for(predicate, *, timeout: float = 1.0):
    async def _inner():
        loop = asyncio.get_running_loop()
        started = loop.time()
        while (loop.time() - started) <= timeout:
            if predicate():
                return True
            await asyncio.sleep(0.01)
        return False

    return _inner()


def test_stream_loop_broadcasts_tick_batch_immediately_on_callback(monkeypatch):
    async def _run():
        _reset_stream_state()

        callbacks = []
        messages: list[dict] = []
        ws_stream.manager.active.add(object())

        async def _capture(message: dict):
            messages.append(dict(message))

        monkeypatch.setattr(ws_stream, "get_settings", lambda: _Settings())
        monkeypatch.setattr(ws_stream, "_fetch_prev_closes", lambda: None)
        monkeypatch.setattr(ws_stream, "_collect_positions", lambda: [])
        monkeypatch.setattr(ws_stream, "_collect_tick_and_positions", lambda _symbols: ([], []))
        monkeypatch.setattr(ws_stream.manager, "broadcast", _capture)
        monkeypatch.setattr(ws_stream.FEED, "subscribe", lambda callback: callbacks.append(callback))
        monkeypatch.setattr(ws_stream.FEED, "start_stream", lambda _symbols: None)

        task = asyncio.create_task(ws_stream.stream_loop())
        try:
            registered = await _wait_for(lambda: len(callbacks) == 1)
            assert registered is True

            callbacks[0]("AAPL", 199.5)

            emitted = await _wait_for(
                lambda: any(
                    msg.get("type") == "tick_batch"
                    and any(item.get("symbol") == "AAPL" for item in msg.get("data", []))
                    for msg in messages
                )
            )
            assert emitted is True
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            _reset_stream_state()

    asyncio.run(_run())


def test_stream_loop_falls_back_to_periodic_polling_when_no_tick_event(monkeypatch):
    async def _run():
        _reset_stream_state()

        messages: list[dict] = []
        ws_stream.manager.active.add(object())

        class _PollingSettings(_Settings):
            ALPACA_STREAM_ENABLED = False
            WEBSOCKET_BROADCAST_INTERVAL = 0.05

        async def _capture(message: dict):
            messages.append(dict(message))

        monkeypatch.setattr(ws_stream, "get_settings", lambda: _PollingSettings())
        monkeypatch.setattr(ws_stream, "_fetch_prev_closes", lambda: None)
        monkeypatch.setattr(
            ws_stream,
            "_collect_tick_and_positions",
            lambda _symbols: (
                [
                    {
                        "symbol": "MSFT",
                        "price": 321.0,
                        "prev_close": 320.0,
                        "change": 1.0,
                        "change_pct": 0.3125,
                        "ts": "2026-01-01T00:00:00Z",
                    }
                ],
                [{"symbol": "MSFT", "qty": 2}],
            ),
        )
        monkeypatch.setattr(ws_stream.manager, "broadcast", _capture)
        monkeypatch.setattr(ws_stream.FEED, "subscribe", lambda _callback: None)

        task = asyncio.create_task(ws_stream.stream_loop())
        try:
            emitted = await _wait_for(
                lambda: any(msg.get("type") == "tick_batch" for msg in messages)
                and any(msg.get("type") == "positions_update" for msg in messages),
                timeout=1.5,
            )
            assert emitted is True
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            _reset_stream_state()

    asyncio.run(_run())
