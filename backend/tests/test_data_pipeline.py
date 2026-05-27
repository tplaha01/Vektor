from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd

import app.data_pipeline.service as pipeline_service_module
from app.config import get_settings
from app.data_pipeline.service import QuantDataPipeline
from app.data_pipeline.warehouse import utc_iso, warehouse
from app.storage import db as storage_db


def test_alpaca_bars_request_fetches_latest_window_in_chronological_order(monkeypatch):
    from app.data.market_data import AlpacaRealtimeFeed

    captured = {}

    def fake_rest_json(path, params):
        captured["path"] = path
        captured["params"] = params
        return {
            "bars": {
                "AAPL": [
                    {"t": "2026-05-15T04:00:00Z", "o": 102, "h": 104, "l": 101, "c": 103, "v": 1_400_000},
                    {"t": "2026-05-14T04:00:00Z", "o": 100, "h": 103, "l": 99, "c": 102, "v": 1_200_000},
                    {"t": "2026-05-13T04:00:00Z", "o": 98, "h": 101, "l": 97, "c": 100, "v": 1_000_000},
                ]
            }
        }

    feed = AlpacaRealtimeFeed()
    monkeypatch.setattr(feed, "_alpaca_rest_json", fake_rest_json)

    frame = feed._alpaca_bars("AAPL", bars=3)

    assert captured["path"] == "/v2/stocks/bars"
    assert captured["params"]["sort"] == "desc"
    assert list(frame["close"]) == [100, 102, 103]


class _FakeFeed:
    def price(self, symbol: str) -> float:
        return 100.0 if symbol == "AAPL" else 50.0

    def history(self, symbol: str, bars: int = 260):
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return pd.DataFrame(
            [
                {
                    "ts": (today - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
                    "open": 98,
                    "high": 101,
                    "low": 97,
                    "close": 100,
                    "volume": 1_000_000,
                },
                {
                    "ts": (today - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                    "open": 100,
                    "high": 103,
                    "low": 99,
                    "close": 102,
                    "volume": 1_200_000,
                },
                {
                    "ts": today.isoformat().replace("+00:00", "Z"),
                    "open": 102,
                    "high": 104,
                    "low": 101,
                    "close": 103,
                    "volume": 1_400_000,
                },
            ]
        )


def test_quant_data_pipeline_persists_canonical_rows_and_features(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "pipeline.db"))
    monkeypatch.setenv("DATA_PIPELINE_ENABLED", "false")
    get_settings.cache_clear()
    storage_db._conn = None
    storage_db.init_db()

    import app.data.market_data as market_data
    import app.data.news as news_data
    import app.data.fundamentals as fundamentals_data

    monkeypatch.setattr(market_data, "FEED", _FakeFeed())
    monkeypatch.setattr(
        news_data,
        "latest_news",
        lambda symbol, limit=8: [
            {
                "symbol": symbol,
                "headline": f"{symbol} earnings beat expectations",
                "source": "UnitTestNews",
                "url": "https://example.com/aapl",
                "published_at": utc_iso(),
            }
        ],
    )
    monkeypatch.setattr(
        fundamentals_data,
        "get_fundamentals",
        lambda symbol: {
            "revenue_growth": 0.12,
            "gross_margin": 0.44,
            "oper_margin": 0.28,
            "debt_to_equity": 0.4,
            "pe": 24.0,
        },
    )

    pipeline = QuantDataPipeline()
    run = pipeline.run_cycle(["AAPL"], run_type="unit_test")

    assert run["status"] == "completed"
    assert run["counts"]["prices"] == 1
    assert run["counts"]["bars"] == 3
    assert run["counts"]["text_events"] == 1
    assert run["counts"]["fundamentals"] == 1
    assert run["counts"]["features"] == 1

    status = warehouse.status()
    assert status["counts"]["data_raw_events"] >= 4
    assert status["counts"]["data_market_prices"] == 1
    assert status["counts"]["data_market_bars"] == 3
    assert status["counts"]["data_text_events"] == 1
    assert status["counts"]["data_fundamentals"] == 1
    assert status["counts"]["data_feature_vectors"] == 1

    features = pipeline.latest_features("AAPL")
    assert features[0]["symbol"] == "AAPL"
    assert features[0]["category"] in {"trade_candidate", "watchlist", "research_only"}
    assert "realized_vol_20d" in features[0]["features"]


def test_realtime_tick_is_persisted_as_execution_feature(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stream.db"))
    get_settings.cache_clear()
    storage_db._conn = None
    storage_db.init_db()

    pipeline = QuantDataPipeline()
    observed_at = utc_iso()
    pipeline.record_realtime_tick(
        "AAPL",
        299.12,
        {
            "symbol": "AAPL",
            "price": 299.12,
            "observed_at": observed_at,
            "size": 100,
            "exchange": "V",
            "trade_id": 12345,
            "feed": "iex",
        },
    )

    status = warehouse.status()
    assert status["counts"]["data_raw_events"] == 1
    assert status["counts"]["data_market_prices"] == 1
    assert status["counts"]["data_feature_vectors"] == 1

    features = pipeline.latest_features("AAPL")
    assert features[0]["use_case"] == "execution"
    assert features[0]["category"] == "live_tick"
    assert features[0]["features"]["last_trade_price"] == 299.12


def test_realtime_quote_is_persisted_as_nbbo_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "quote.db"))
    get_settings.cache_clear()
    storage_db._conn = None
    storage_db.init_db()

    pipeline = QuantDataPipeline()
    observed_at = utc_iso()
    pipeline.record_realtime_quote(
        "AAPL",
        {
            "event_type": "quote",
            "symbol": "AAPL",
            "bid_price": 299.1,
            "bid_size": 4,
            "ask_price": 299.14,
            "ask_size": 6,
            "observed_at": observed_at,
            "feed": "iex",
        },
    )

    status = warehouse.status()
    assert status["counts"]["data_raw_events"] == 1
    assert status["counts"]["data_market_quotes"] == 1
    assert status["counts"]["data_feature_vectors"] == 1

    health = warehouse.provider_health()
    assert health[0]["provider"] == "alpaca_quote_stream"
    assert health[0]["status"] == "healthy"

    snapshots = warehouse.latest_rows("data_snapshots", limit=1)
    assert snapshots[0]["snapshot_type"] == "nbbo"
    replay = pipeline.replay_snapshot(snapshots[0]["snapshot_id"])
    assert replay is not None
    assert replay["payload"]["mid_price"] == 299.12


def test_stale_bars_are_quality_flagged_and_block_features(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stale.db"))
    monkeypatch.setenv("DATA_PIPELINE_MAX_BAR_AGE_DAYS", "1")
    get_settings.cache_clear()
    storage_db._conn = None
    storage_db.init_db()

    import app.data.market_data as market_data
    import app.data.news as news_data
    import app.data.fundamentals as fundamentals_data

    class _StaleFeed(_FakeFeed):
        def history(self, symbol: str, bars: int = 260):
            return pd.DataFrame(
                [
                    {
                        "ts": "2025-12-26T05:00:00Z",
                        "open": 100,
                        "high": 101,
                        "low": 99,
                        "close": 100,
                        "volume": 1_000_000,
                    }
                ]
            )

    monkeypatch.setattr(market_data, "FEED", _StaleFeed())
    monkeypatch.setattr(news_data, "latest_news", lambda symbol, limit=8: [])
    monkeypatch.setattr(fundamentals_data, "get_fundamentals", lambda symbol: {})

    pipeline = QuantDataPipeline()
    run = pipeline.run_cycle(["AAPL"], run_type="stale_unit_test")

    assert "stale_observation" in run["quality"]["AAPL"]["bars"]["flags"]
    features = pipeline.latest_features("AAPL")
    assert features[0]["category"] == "stale_blocked"
    assert features[0]["metadata"]["stale_bar_blocked"] is True


def test_realtime_news_is_persisted_as_text_event(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "news-stream.db"))
    get_settings.cache_clear()
    storage_db._conn = None
    storage_db.init_db()

    pipeline = QuantDataPipeline()
    created_at = utc_iso()
    pipeline.record_realtime_news(
        {
            "id": "news-1",
            "headline": "AAPL launches new institutional product",
            "summary": "AAPL announced a new product for institutional clients.",
            "author": "Unit Test",
            "url": "https://example.com/news-1",
            "symbols": ["AAPL"],
            "created_at": created_at,
        }
    )

    status = warehouse.status()
    assert status["counts"]["data_raw_events"] == 1
    assert status["counts"]["data_text_events"] == 1


def test_news_stream_skipped_when_market_stream_enabled_and_parallel_guard_active(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    monkeypatch.setenv("ALPACA_STREAM_ENABLED", "true")
    monkeypatch.setenv("DATA_PIPELINE_NEWS_STREAM_ENABLED", "true")
    monkeypatch.setenv("DATA_PIPELINE_NEWS_STREAM_ALLOW_PARALLEL_ALPACA_WS", "false")
    get_settings.cache_clear()

    pipeline = QuantDataPipeline()
    pipeline._start_news_stream()

    assert pipeline._news_stream_started is False
    assert pipeline._news_stream_disable_reason == "parallel_alpaca_ws_disabled"
    get_settings.cache_clear()


def test_news_stream_can_start_when_parallel_guard_is_overridden(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    monkeypatch.setenv("ALPACA_STREAM_ENABLED", "true")
    monkeypatch.setenv("DATA_PIPELINE_NEWS_STREAM_ENABLED", "true")
    monkeypatch.setenv("DATA_PIPELINE_NEWS_STREAM_ALLOW_PARALLEL_ALPACA_WS", "true")
    get_settings.cache_clear()

    starts = {"count": 0}

    class _StubThread:
        def __init__(self, target, daemon, name):
            self.target = target
            self.daemon = daemon
            self.name = name

        def start(self):
            starts["count"] += 1

    monkeypatch.setattr(pipeline_service_module.threading, "Thread", _StubThread)

    pipeline = QuantDataPipeline()
    pipeline._start_news_stream()

    assert starts["count"] == 1
    assert pipeline._news_stream_started is True
    assert pipeline._news_stream_disable_reason is None
    get_settings.cache_clear()


def test_pipeline_start_owns_live_market_stream(monkeypatch):
    monkeypatch.setenv("ALPACA_STREAM_ENABLED", "true")
    monkeypatch.setenv("DATA_PIPELINE_NEWS_STREAM_ENABLED", "false")
    get_settings.cache_clear()

    starts: list[tuple[str, ...]] = []
    subscriptions = {"count": 0}

    class _StreamFeed:
        def subscribe(self, callback):
            subscriptions["count"] += 1

        def start_stream(self, symbols):
            starts.append(tuple(symbols))

    import app.data.market_data as market_data

    monkeypatch.setattr(market_data, "FEED", _StreamFeed())

    async def _run():
        pipeline = QuantDataPipeline()
        await pipeline.start()
        try:
            status = pipeline.status()
            assert starts == [tuple(pipeline.configured_symbols())]
            assert subscriptions["count"] == 1
            assert status["mode"] == "live_stream_first"
            assert status["scheduled_rest_cycles_enabled"] is False
            assert status["stream"]["started"] is True
        finally:
            await pipeline.stop()

    asyncio.run(_run())
    get_settings.cache_clear()


def test_stream_first_loop_does_not_run_scheduled_rest_cycle(monkeypatch):
    monkeypatch.setenv("ALPACA_STREAM_ENABLED", "true")
    get_settings.cache_clear()

    async def _run():
        pipeline = QuantDataPipeline()
        pipeline._running = True
        pipeline._stream_subscribed = True
        calls = {"count": 0}

        def _unexpected_cycle(*_args, **_kwargs):
            calls["count"] += 1

        monkeypatch.setattr(pipeline, "run_cycle", _unexpected_cycle)
        task = asyncio.create_task(pipeline._run_loop())
        await asyncio.sleep(0.05)
        pipeline._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert calls["count"] == 0
        assert pipeline.status()["mode"] == "live_stream_first"

    asyncio.run(_run())
    get_settings.cache_clear()


def test_rest_polling_loop_is_only_disabled_stream_fallback(monkeypatch):
    monkeypatch.setenv("ALPACA_STREAM_ENABLED", "false")
    monkeypatch.setenv("DATA_PIPELINE_INTERVAL_SECONDS", "5")
    get_settings.cache_clear()

    async def _run():
        pipeline = QuantDataPipeline()
        pipeline._running = True
        calls: list[tuple[list[str], str]] = []

        def _capture_cycle(symbols, run_type):
            calls.append((list(symbols), run_type))
            pipeline._running = False
            return {"status": "completed"}

        monkeypatch.setattr(pipeline, "run_cycle", _capture_cycle)
        task = asyncio.create_task(pipeline._run_loop())
        await asyncio.wait_for(task, timeout=1.0)

        assert len(calls) == 1
        assert calls[0][1] == "fallback_polling"
        status = pipeline.status()
        assert status["mode"] == "rest_fallback"
        assert status["scheduled_rest_cycles_enabled"] is True

    asyncio.run(_run())
    get_settings.cache_clear()
