from __future__ import annotations

from typing import Any

from app.core_engine.domain_models.fundamental_pack import run_fundamental_pack
from app.core_engine.domain_models.sentiment_pack import run_sentiment_pack
from app.core_engine.domain_models.technical_pack import run_technical_pack
from app.core_engine.feature_store import build_point_in_time_snapshot
from app.core_engine.stacking.meta_intent import run_meta_intent


def build_point_in_time_dataset(symbols: list[str], profile: str = "balanced") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        snapshot = build_point_in_time_snapshot(symbol=symbol, profile=profile)
        technical = run_technical_pack(snapshot)
        fundamental = run_fundamental_pack(snapshot)
        sentiment = run_sentiment_pack(snapshot)
        meta = run_meta_intent(profile, technical, fundamental, sentiment)
        rows.append(
            {
                "symbol": snapshot.symbol,
                "as_of": snapshot.as_of,
                "profile": profile,
                "run_id": snapshot.lineage["run_id"],
                "decision_id": snapshot.lineage["decision_id"],
                "feature_hash": snapshot.lineage["feature_hash"],
                "technical_alpha": technical.alpha,
                "fundamental_alpha": fundamental.alpha,
                "sentiment_alpha": sentiment.alpha,
                "intent_score": meta.intent_score,
                "intent_confidence": meta.confidence,
                "expected_utility": meta.expected_utility,
            }
        )
    return rows
