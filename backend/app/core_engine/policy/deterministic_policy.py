from __future__ import annotations

from app.config import get_settings
from app.core_engine.contracts import EngineInputSnapshot, MetaIntentOutput, PolicyDecision
from app.core_engine.registry.model_registry import get_profile

_REQUIRED_MODEL_KEYS = ("technical_pack", "fundamental_pack", "sentiment_pack", "meta_intent", "policy")


def _max_optional(limit_a: float | None, limit_b: float | None) -> float | None:
    if limit_a is None:
        return limit_b
    if limit_b is None:
        return limit_a
    return min(float(limit_a), float(limit_b))


def apply_deterministic_policy(snapshot: EngineInputSnapshot, meta: MetaIntentOutput) -> PolicyDecision:
    settings = get_settings()
    profile = get_profile(snapshot.profile)

    rejections: list[str] = []
    quality_flags = set(snapshot.freshness.quality_flags)
    freshness = snapshot.freshness

    if "insufficient_market_history" in quality_flags:
        rejections.append("insufficient_market_history")
    if freshness.market_age_minutes is not None:
        market_age_limit = float(settings.CORE_ENGINE_MAX_MARKET_AGE_MINUTES)
        if freshness.market_age_minutes > market_age_limit:
            rejections.append("stale_market_data")

    require_fundamentals = bool(settings.CORE_ENGINE_REQUIRE_FUNDAMENTALS or profile.require_fundamentals)
    require_sentiment = bool(settings.CORE_ENGINE_REQUIRE_SENTIMENT or profile.require_sentiment)

    if require_fundamentals and "fundamentals_incomplete" in quality_flags:
        rejections.append("fundamentals_required_missing")
    if require_sentiment and "sentiment_news_missing" in quality_flags:
        rejections.append("sentiment_required_missing")

    fundamentals_age_limit = _max_optional(
        float(settings.CORE_ENGINE_MAX_FUNDAMENTALS_AGE_HOURS),
        profile.max_fundamentals_age_hours,
    )
    if fundamentals_age_limit is not None and freshness.fundamentals_age_hours is not None:
        if freshness.fundamentals_age_hours > fundamentals_age_limit:
            rejections.append("stale_fundamentals_data")
    if require_fundamentals and freshness.fundamentals_age_hours is None:
        rejections.append("fundamentals_timestamp_missing")

    sentiment_age_limit = _max_optional(
        float(settings.CORE_ENGINE_MAX_SENTIMENT_AGE_MINUTES),
        profile.max_sentiment_age_minutes,
    )
    if sentiment_age_limit is not None and freshness.sentiment_age_minutes is not None:
        if freshness.sentiment_age_minutes > sentiment_age_limit:
            rejections.append("stale_sentiment_data")

    model_versions = snapshot.model_versions if isinstance(snapshot.model_versions, dict) else {}
    missing_model_keys = [key for key in _REQUIRED_MODEL_KEYS if not str(model_versions.get(key) or "").strip()]
    if missing_model_keys:
        rejections.append("model_versions_missing")

    min_conf_threshold = max(float(settings.CORE_ENGINE_MIN_CONFIDENCE), float(profile.min_confidence))
    if float(meta.confidence) < min_conf_threshold:
        rejections.append("confidence_below_threshold")

    uncertainty_limit = min(
        float(settings.CORE_ENGINE_MAX_AGGREGATE_UNCERTAINTY),
        float(profile.max_aggregate_uncertainty),
    )
    aggregate_uncertainty = float(meta.diagnostics.get("aggregate_uncertainty", 1.0))
    if aggregate_uncertainty > uncertainty_limit:
        rejections.append("aggregate_uncertainty_above_threshold")

    expected_utility_threshold = max(
        float(settings.CORE_ENGINE_MIN_EXPECTED_UTILITY),
        float(profile.min_expected_utility),
    )
    if float(meta.expected_utility) < expected_utility_threshold:
        rejections.append("expected_utility_below_threshold")

    atr_pct = 0.0
    if snapshot.history is not None and len(snapshot.history) > 0:
        high_last = float(snapshot.history["high"].tail(1).iloc[0])
        low_last = float(snapshot.history["low"].tail(1).iloc[0])
        close_last = float(snapshot.history["close"].tail(1).iloc[0])
        atr_pct = float((high_last - low_last) / max(close_last, 1e-9))
    if atr_pct > float(settings.VOL_THRESHOLD) * float(profile.volatility_multiplier):
        rejections.append("volatility_gate")

    if rejections:
        return PolicyDecision(
            action="hold",
            safe_mode=True,
            rejections=sorted(set(rejections)),
            diagnostics={
                "profile": profile.name,
                "quality_flags": sorted(quality_flags),
                "missing_model_keys": missing_model_keys,
                "thresholds": {
                    "min_confidence": min_conf_threshold,
                    "max_aggregate_uncertainty": uncertainty_limit,
                    "min_expected_utility": expected_utility_threshold,
                    "max_market_age_minutes": float(settings.CORE_ENGINE_MAX_MARKET_AGE_MINUTES),
                    "max_sentiment_age_minutes": sentiment_age_limit,
                    "max_fundamentals_age_hours": fundamentals_age_limit,
                    "max_volatility_pct": float(settings.VOL_THRESHOLD) * float(profile.volatility_multiplier),
                },
                "atr_pct": atr_pct,
            },
        )

    action = "hold"
    if float(meta.intent_score) > float(settings.BUY_THRESHOLD):
        action = "buy"
    elif float(meta.intent_score) < float(settings.SELL_THRESHOLD):
        action = "sell"

    return PolicyDecision(
        action=action,
        safe_mode=False,
        rejections=[],
        diagnostics={
            "profile": profile.name,
            "quality_flags": sorted(quality_flags),
            "thresholds": {
                "min_confidence": min_conf_threshold,
                "max_aggregate_uncertainty": uncertainty_limit,
                "min_expected_utility": expected_utility_threshold,
            },
            "atr_pct": atr_pct,
        },
    )
