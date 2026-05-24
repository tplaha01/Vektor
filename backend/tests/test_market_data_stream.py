from __future__ import annotations

import asyncio

import app.data.market_data as market_data


def test_stream_connection_limit_switches_to_rest_fallback(monkeypatch):
    class _Settings:
        ALPACA_API_KEY = "test-key"
        ALPACA_SECRET_KEY = "test-secret"
        ALPACA_FEED = "iex"
        ALPACA_HTTP_RETRIES = 1
        ALPACA_HTTP_TIMEOUT_SECONDS = 2.0
        ALPACA_HTTP_RETRY_BACKOFF_SECONDS = 0.0

    class _FakeDataFeed:
        IEX = "IEX"
        SIP = "SIP"

    class _FakeStockDataStream:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)
            self._connect = self._orig_connect
            self._auth = self._orig_auth

        async def _orig_connect(self):
            raise ValueError("connection limit exceeded")

        async def _orig_auth(self):
            return None

        def subscribe_trades(self, handler, *symbols):
            _ = (handler, symbols)

        def subscribe_quotes(self, handler, *symbols):
            _ = (handler, symbols)

        def run(self):
            async def _once():
                try:
                    await self._connect()
                    await self._auth()
                except ValueError:
                    return

            asyncio.run(_once())

    events: list[dict] = []

    monkeypatch.setattr(market_data, "settings", _Settings())
    monkeypatch.setattr(
        market_data.data_integrity_guard,
        "record_provider_event",
        lambda **kwargs: events.append(dict(kwargs)),
    )
    monkeypatch.setattr("alpaca.data.live.StockDataStream", _FakeStockDataStream)
    monkeypatch.setattr("alpaca.data.enums.DataFeed", _FakeDataFeed)

    feed = market_data.AlpacaRealtimeFeed()
    feed._started = True
    feed._run_stream(["AAPL"])

    assert feed._started is False
    assert any(
        row.get("provider") == "alpaca_stream"
        and row.get("mode") == "fallback"
        and row.get("detail") == "stream_connection_limit_exceeded"
        for row in events
    )
