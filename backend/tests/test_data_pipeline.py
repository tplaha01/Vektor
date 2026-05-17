from __future__ import annotations

import pandas as pd

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
        return pd.DataFrame(
            [
                {"ts": "2026-05-13T00:00:00Z", "open": 98, "high": 101, "low": 97, "close": 100, "volume": 1_000_000},
                {"ts": "2026-05-14T00:00:00Z", "open": 100, "high": 103, "low": 99, "close": 102, "volume": 1_200_000},
                {"ts": "2026-05-15T00:00:00Z", "open": 102, "high": 104, "low": 101, "close": 103, "volume": 1_400_000},
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
                "published_at": "2026-05-15T09:00:00Z",
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
