from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Profile:
    name: str
    stack_weights: dict[str, float]
    min_confidence: float
    volatility_multiplier: float
    max_sentiment_age_minutes: float
    max_fundamentals_age_hours: float
    max_aggregate_uncertainty: float
    min_expected_utility: float
    require_fundamentals: bool
    require_sentiment: bool


_PROFILES: dict[str, Profile] = {
    "accuracy_max": Profile(
        name="accuracy_max",
        stack_weights={"technical": 0.33, "fundamental": 0.29, "sentiment": 0.38},
        min_confidence=0.58,
        volatility_multiplier=0.9,
        max_sentiment_age_minutes=240.0,
        max_fundamentals_age_hours=72.0,
        max_aggregate_uncertainty=0.58,
        min_expected_utility=0.06,
        require_fundamentals=True,
        require_sentiment=True,
    ),
    "balanced": Profile(
        name="balanced",
        stack_weights={"technical": 0.38, "fundamental": 0.34, "sentiment": 0.28},
        min_confidence=0.52,
        volatility_multiplier=1.0,
        max_sentiment_age_minutes=360.0,
        max_fundamentals_age_hours=120.0,
        max_aggregate_uncertainty=0.68,
        min_expected_utility=0.03,
        require_fundamentals=True,
        require_sentiment=False,
    ),
    "latency_low": Profile(
        name="latency_low",
        stack_weights={"technical": 0.52, "fundamental": 0.30, "sentiment": 0.18},
        min_confidence=0.5,
        volatility_multiplier=1.15,
        max_sentiment_age_minutes=720.0,
        max_fundamentals_age_hours=168.0,
        max_aggregate_uncertainty=0.75,
        min_expected_utility=0.02,
        require_fundamentals=False,
        require_sentiment=False,
    ),
    "risk_off": Profile(
        name="risk_off",
        stack_weights={"technical": 0.30, "fundamental": 0.42, "sentiment": 0.28},
        min_confidence=0.62,
        volatility_multiplier=0.8,
        max_sentiment_age_minutes=300.0,
        max_fundamentals_age_hours=72.0,
        max_aggregate_uncertainty=0.52,
        min_expected_utility=0.08,
        require_fundamentals=True,
        require_sentiment=True,
    ),
}


def get_profile(name: str | None) -> Profile:
    key = str(name or "balanced").strip().lower()
    return _PROFILES.get(key, _PROFILES["balanced"])


def list_profiles() -> list[dict[str, Any]]:
    return [
        {
            "name": profile.name,
            "stack_weights": dict(profile.stack_weights),
            "min_confidence": profile.min_confidence,
            "volatility_multiplier": profile.volatility_multiplier,
            "max_sentiment_age_minutes": profile.max_sentiment_age_minutes,
            "max_fundamentals_age_hours": profile.max_fundamentals_age_hours,
            "max_aggregate_uncertainty": profile.max_aggregate_uncertainty,
            "min_expected_utility": profile.min_expected_utility,
            "require_fundamentals": profile.require_fundamentals,
            "require_sentiment": profile.require_sentiment,
        }
        for profile in _PROFILES.values()
    ]


def get_active_model_versions(profile_name: str | None) -> dict[str, str]:
    profile = get_profile(profile_name)
    return {
        "profile": profile.name,
        "technical_pack": "market-pack-v2.0.0",
        "market_pack": "market-pack-v2.0.0",
        "fundamental_pack": "fundamental-pack-ml-v2.0.0",
        "sentiment_pack": "sentiment-v1.0.0",
        "meta_intent": "meta-intent-v1.0.0",
        "policy": "deterministic-policy-v1.0.0",
    }
