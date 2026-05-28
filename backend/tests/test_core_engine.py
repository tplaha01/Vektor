from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.core_engine import run_core_engine
from app.core_engine import feature_store
from app.config import get_settings
from app.core_engine.routing import profile_router
from app.data_pipeline.service import QuantDataPipeline
from app.data_pipeline.warehouse import utc_iso
from app.quant.types import MarketRegimeSnapshot
from app.storage import db as storage_db
from app.strategies.deterministic_ml_engine import deterministic_signal


def _history_frame(bars: int) -> pd.DataFrame:
    ts = pd.date_range(end=datetime.now(timezone.utc), periods=bars, freq="5min")
    close = np.linspace(100.0, 108.0, bars) + np.sin(np.arange(bars) / 7.0)
    return pd.DataFrame(
        {
            "ts": ts,
            "open": close - 0.25,
            "high": close + 0.50,
            "low": close - 0.50,
            "close": close,
            "volume": np.linspace(1_000, 2_000, bars),
        }
    )


def test_core_engine_emits_contract_payload(monkeypatch):
    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(min(220, bars)))
    monkeypatch.setattr(
        feature_store,
        "get_fundamentals",
        lambda symbol: {
            "revenue_growth": 0.11,
            "gross_margin": 0.44,
            "oper_margin": 0.27,
            "debt_to_equity": 0.9,
            "pe": 24.0,
        },
    )
    monkeypatch.setattr(
        feature_store,
        "latest_news",
        lambda symbol, limit=24: [
            {
                "symbol": symbol,
                "headline": "Company posts strong quarter and raises guidance",
                "source": "Reuters",
                "url": "",
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )

    out = run_core_engine("AAPL", profile="balanced").to_dict()
    assert out["symbol"] == "AAPL"
    assert "score" in out and -1.0 <= out["score"] <= 1.0
    assert out["action"] in {"buy", "sell", "hold"}
    assert 0.0 <= out["confidence"] <= 1.0
    assert "lineage" in out["diagnostics"]
    assert "policy" in out["diagnostics"]
    assert "profile_routing" in out["diagnostics"]
    assert out["diagnostics"]["signal_pipeline_only"] is True
    assert out["diagnostics"]["llm_signal_path"] is False
    assert out["diagnostics"]["market_pack_inference"] is True
    technical_diag = out["diagnostics"]["technical"]
    assert str(technical_diag.get("inference_mode") or "").startswith("learned_market_pack")
    assert technical_diag.get("legacy_indicator_scoring") is False
    fundamental_diag = out["diagnostics"]["fundamental"]
    assert fundamental_diag.get("inference_mode") == "learned_fundamental_pack_linear"
    assert fundamental_diag.get("legacy_rule_scoring") is False
    assert "feature_hash" in out["diagnostics"]["lineage"]
    assert "contract_hash" in out["diagnostics"]["determinism"]
    assert out["model"]["mandatory_ml"] is True
    assert isinstance(out["diagnostics"]["reason_codes"], list)


def test_core_engine_safe_mode_on_insufficient_history(monkeypatch):
    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(24))
    monkeypatch.setattr(feature_store, "get_fundamentals", lambda symbol: {})
    monkeypatch.setattr(feature_store, "latest_news", lambda symbol, limit=24: [])

    out = run_core_engine("AAPL", profile="risk_off").to_dict()
    assert out["action"] == "hold"
    assert out["diagnostics"]["policy"]["safe_mode"] is True
    assert "insufficient_market_history" in out["diagnostics"]["policy"]["rejections"]
    assert "fundamentals_required_missing" in out["diagnostics"]["policy"]["rejections"]
    assert "size_multiplier" not in out["diagnostics"]["policy"]


def test_legacy_deterministic_signal_routes_through_core_engine(monkeypatch):
    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(min(220, bars)))
    monkeypatch.setattr(feature_store, "get_fundamentals", lambda symbol: {"revenue_growth": 0.1, "gross_margin": 0.4})
    monkeypatch.setattr(feature_store, "latest_news", lambda symbol, limit=24: [])

    out = deterministic_signal("AAPL").to_dict()
    assert out["symbol"] == "AAPL"
    assert "signal_pipeline_only" in out["diagnostics"]
    assert out["diagnostics"]["signal_pipeline_only"] is True


def test_core_engine_contract_hash_is_deterministic_for_same_snapshot(monkeypatch):
    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(min(220, bars)))
    monkeypatch.setattr(
        feature_store,
        "get_fundamentals",
        lambda symbol: {
            "revenue_growth": 0.08,
            "gross_margin": 0.41,
            "oper_margin": 0.22,
            "debt_to_equity": 0.85,
            "pe": 21.0,
            "updated_at": "2026-05-22T20:00:00Z",
        },
    )
    monkeypatch.setattr(
        feature_store,
        "latest_news",
        lambda symbol, limit=24: [
            {
                "symbol": symbol,
                "headline": "Company launches a major enterprise product expansion",
                "source": "Reuters",
                "url": "",
                "published_at": "2026-05-22T21:00:00Z",
            },
            {
                "symbol": symbol,
                "headline": "Analysts reiterate positive guidance after update",
                "source": "Bloomberg",
                "url": "",
                "published_at": "2026-05-22T18:00:00Z",
            },
        ],
    )

    first = run_core_engine("AAPL", profile="balanced").to_dict()
    second = run_core_engine("AAPL", profile="balanced").to_dict()
    assert first["score"] == second["score"]
    assert first["confidence"] == second["confidence"]
    assert first["action"] == second["action"]
    assert first["diagnostics"]["lineage"]["feature_hash"] == second["diagnostics"]["lineage"]["feature_hash"]
    assert first["diagnostics"]["determinism"]["contract_hash"] == second["diagnostics"]["determinism"]["contract_hash"]


def test_core_engine_disables_polarity_only_sentiment_model(monkeypatch):
    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(min(220, bars)))
    monkeypatch.setattr(
        feature_store,
        "get_fundamentals",
        lambda symbol: {
            "revenue_growth": 0.08,
            "gross_margin": 0.41,
            "oper_margin": 0.22,
            "debt_to_equity": 0.85,
            "pe": 21.0,
            "updated_at": "2026-05-22T20:00:00Z",
        },
    )
    monkeypatch.setattr(
        feature_store,
        "latest_news",
        lambda symbol, limit=24: [
            {
                "symbol": symbol,
                "headline": "Major earnings surprise and forward guidance revision",
                "source": "Reuters",
                "url": "",
                "published_at": "2026-05-22T21:00:00Z",
            }
        ],
    )
    monkeypatch.setattr("app.core_engine.domain_models.sentiment_pack.sentiment_model_name", lambda: "VADER")

    out = run_core_engine("AAPL", profile="balanced").to_dict()
    sentiment_diag = out["diagnostics"]["sentiment"]
    assert sentiment_diag["reason"] == "polarity_only_model_disabled"
    assert sentiment_diag["authoritative_for_signal"] is False
    assert out["subscores"]["sentiment"] == 0.0


def test_core_engine_rejects_stale_sentiment_when_profile_requires_it(monkeypatch):
    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(min(220, bars)))
    monkeypatch.setattr(
        feature_store,
        "get_fundamentals",
        lambda symbol: {
            "revenue_growth": 0.09,
            "gross_margin": 0.40,
            "oper_margin": 0.21,
            "debt_to_equity": 0.95,
            "pe": 23.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    stale_ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    monkeypatch.setattr(
        feature_store,
        "latest_news",
        lambda symbol, limit=24: [
            {
                "symbol": symbol,
                "headline": "Legacy sentiment source remains stale",
                "source": "Reuters",
                "url": "",
                "published_at": stale_ts,
            }
        ],
    )

    out = run_core_engine("AAPL", profile="accuracy_max").to_dict()
    assert out["action"] == "hold"
    assert out["diagnostics"]["policy"]["safe_mode"] is True
    assert "stale_sentiment_data" in out["diagnostics"]["policy"]["rejections"]


def test_core_engine_snapshot_prefers_latest_stream_price(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "core-stream.db"))
    get_settings.cache_clear()
    storage_db._conn = None
    storage_db.init_db()

    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(min(220, bars)))
    monkeypatch.setattr(
        feature_store,
        "get_fundamentals",
        lambda symbol: {
            "revenue_growth": 0.08,
            "gross_margin": 0.41,
            "oper_margin": 0.22,
            "debt_to_equity": 0.85,
            "pe": 21.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    monkeypatch.setattr(
        feature_store,
        "latest_news",
        lambda symbol, limit=24: [
            {
                "symbol": symbol,
                "headline": "Latest institutional flow is constructive",
                "source": "UnitTestNews",
                "url": "",
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )

    QuantDataPipeline().record_realtime_tick(
        "AAPL",
        199.75,
        {
            "symbol": "AAPL",
            "price": 199.75,
            "observed_at": utc_iso(),
            "size": 25,
            "exchange": "V",
            "feed": "iex",
        },
    )

    snapshot = feature_store.build_point_in_time_snapshot("AAPL", profile="balanced")

    assert float(snapshot.history["close"].iloc[-1]) == 199.75
    assert snapshot.freshness.market_age_minutes is not None
    assert snapshot.freshness.market_age_minutes < 0.01
    get_settings.cache_clear()


def test_core_engine_auto_routes_directional_regime_to_latency_low(monkeypatch):
    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(min(220, bars)))
    monkeypatch.setattr(
        feature_store,
        "get_fundamentals",
        lambda symbol: {
            "revenue_growth": 0.11,
            "gross_margin": 0.44,
            "oper_margin": 0.27,
            "debt_to_equity": 0.9,
            "pe": 24.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    monkeypatch.setattr(
        feature_store,
        "latest_news",
        lambda symbol, limit=24: [
            {
                "symbol": symbol,
                "headline": "Momentum remains strong after institutional accumulation",
                "source": "Reuters",
                "url": "",
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    monkeypatch.setattr(
        profile_router,
        "infer_market_regime",
        lambda df: MarketRegimeSnapshot(
            regime="TREND_UP",
            direction="long_bias",
            confidence=0.84,
            edge=0.39,
            trend_score=0.8,
            breakout_score=0.2,
            mean_reversion_score=0.0,
            volatility_score=0.44,
            liquidity_score=0.8,
            adx=31.0,
            atr_pct=0.018,
            realised_vol_20d=0.22,
            rsi=63.0,
            volume_ratio=1.35,
            notes=("adx_trend",),
            metrics={},
        ),
    )

    out = run_core_engine("AAPL").to_dict()
    routing = out["diagnostics"]["profile_routing"]
    assert routing["mode"] == "auto"
    assert routing["requested_profile"] == "auto"
    assert routing["active_profile"] == "latency_low"
    assert "directional_regime" in routing["reasons"]
    assert out["model"]["profile"] == "latency_low"


def test_core_engine_explicit_profile_bypasses_auto_router(monkeypatch):
    monkeypatch.setattr(feature_store.FEED, "history", lambda symbol, bars=320: _history_frame(min(220, bars)))
    monkeypatch.setattr(
        feature_store,
        "get_fundamentals",
        lambda symbol: {
            "revenue_growth": 0.11,
            "gross_margin": 0.44,
            "oper_margin": 0.27,
            "debt_to_equity": 0.9,
            "pe": 24.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    monkeypatch.setattr(
        feature_store,
        "latest_news",
        lambda symbol, limit=24: [
            {
                "symbol": symbol,
                "headline": "Momentum remains strong after institutional accumulation",
                "source": "Reuters",
                "url": "",
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    monkeypatch.setattr(
        profile_router,
        "infer_market_regime",
        lambda df: MarketRegimeSnapshot(
            regime="HIGH_VOL",
            direction="neutral",
            confidence=0.88,
            edge=0.02,
            trend_score=0.1,
            breakout_score=0.0,
            mean_reversion_score=0.0,
            volatility_score=0.93,
            liquidity_score=0.7,
            adx=16.0,
            atr_pct=0.052,
            realised_vol_20d=0.46,
            rsi=51.0,
            volume_ratio=1.1,
            notes=("volatility_orderly",),
            metrics={},
        ),
    )

    out = run_core_engine("AAPL", profile="balanced").to_dict()
    routing = out["diagnostics"]["profile_routing"]
    assert routing["mode"] == "fixed"
    assert routing["requested_profile"] == "balanced"
    assert routing["active_profile"] == "balanced"
    assert routing["reasons"] == ["explicit_profile"]
    assert out["model"]["profile"] == "balanced"
