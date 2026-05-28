from __future__ import annotations

from typing import Any

from app.core_engine.contracts import EngineInputSnapshot
from app.quant.regime import infer_market_regime

AUTO_PROFILE_NAME = "auto"
_KNOWN_PROFILES = {"accuracy_max", "balanced", "latency_low", "risk_off"}


def _normalize_base_profile(profile: str | None) -> str:
    key = str(profile or "").strip().lower()
    return key if key in _KNOWN_PROFILES else "balanced"


def _normalize_requested_profile(profile: str | None) -> str:
    key = str(profile or "").strip().lower()
    if not key:
        return AUTO_PROFILE_NAME
    if key == AUTO_PROFILE_NAME:
        return AUTO_PROFILE_NAME
    if key in _KNOWN_PROFILES:
        return key
    return "balanced"


def resolve_profile_routing(
    snapshot: EngineInputSnapshot,
    *,
    requested_profile: str | None,
    base_profile: str | None,
) -> dict[str, Any]:
    requested = _normalize_requested_profile(requested_profile)
    base = _normalize_base_profile(base_profile)

    if requested != AUTO_PROFILE_NAME:
        return {
            "mode": "fixed",
            "requested_profile": requested,
            "base_profile": base,
            "active_profile": requested,
            "reasons": ["explicit_profile"],
            "inputs": {
                "history_bars": int(len(snapshot.history)),
                "sentiment_age_minutes": snapshot.freshness.sentiment_age_minutes,
                "fundamentals_age_hours": snapshot.freshness.fundamentals_age_hours,
            },
        }

    if len(snapshot.history) < 80:
        return {
            "mode": "auto",
            "requested_profile": requested,
            "base_profile": base,
            "active_profile": base,
            "reasons": ["insufficient_history_fallback"],
            "inputs": {
                "history_bars": int(len(snapshot.history)),
                "sentiment_age_minutes": snapshot.freshness.sentiment_age_minutes,
                "fundamentals_age_hours": snapshot.freshness.fundamentals_age_hours,
            },
        }

    regime = infer_market_regime(snapshot.history)
    sentiment_age = snapshot.freshness.sentiment_age_minutes
    fundamentals_age = snapshot.freshness.fundamentals_age_hours
    has_fresh_sentiment = sentiment_age is not None and sentiment_age <= 240.0
    has_fresh_fundamentals = fundamentals_age is not None and fundamentals_age <= 72.0
    strong_directional = (
        regime.regime.startswith(("TREND", "BREAKOUT"))
        and regime.confidence >= 0.58
        and abs(float(regime.edge)) >= 0.15
        and regime.liquidity_score >= 0.35
    )
    stressed_regime = (
        regime.regime == "HIGH_VOL"
        or (regime.direction == "neutral" and regime.confidence >= 0.72 and abs(float(regime.edge)) < 0.12)
        or regime.volatility_score >= 0.82
    )
    research_rich = has_fresh_sentiment and has_fresh_fundamentals and regime.confidence >= 0.45 and abs(float(regime.edge)) >= 0.08

    active_profile = base
    reasons = ["fallback_base_profile"]
    if stressed_regime:
        active_profile = "risk_off"
        reasons = ["high_volatility_regime", f"regime_{str(regime.regime).lower()}"]
    elif strong_directional:
        active_profile = "latency_low"
        reasons = ["directional_regime", f"regime_{str(regime.regime).lower()}"]
    elif research_rich:
        active_profile = "accuracy_max"
        reasons = ["fresh_cross_domain_inputs", f"regime_{str(regime.regime).lower()}"]

    return {
        "mode": "auto",
        "requested_profile": requested,
        "base_profile": base,
        "active_profile": active_profile,
        "reasons": reasons,
        "regime": regime.to_dict(),
        "inputs": {
            "history_bars": int(len(snapshot.history)),
            "sentiment_age_minutes": sentiment_age,
            "fundamentals_age_hours": fundamentals_age,
            "has_fresh_sentiment": has_fresh_sentiment,
            "has_fresh_fundamentals": has_fresh_fundamentals,
        },
    }


__all__ = ["AUTO_PROFILE_NAME", "resolve_profile_routing"]
