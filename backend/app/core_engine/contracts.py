from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class DataFreshness:
    as_of: str
    market_age_minutes: float | None
    sentiment_age_minutes: float | None
    fundamentals_age_hours: float | None
    quality_flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "market_age_minutes": self.market_age_minutes,
            "sentiment_age_minutes": self.sentiment_age_minutes,
            "fundamentals_age_hours": self.fundamentals_age_hours,
            "quality_flags": list(self.quality_flags),
        }


@dataclass
class EngineInputSnapshot:
    symbol: str
    as_of: str
    profile: str
    history: pd.DataFrame
    fundamentals: dict[str, Any]
    news: list[dict[str, Any]]
    freshness: DataFreshness
    lineage: dict[str, str]
    model_versions: dict[str, str]


@dataclass
class DomainModelOutput:
    name: str
    alpha: float
    uncertainty: float
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "alpha": round(float(self.alpha), 6),
            "uncertainty": round(float(self.uncertainty), 6),
            "diagnostics": self.diagnostics,
        }


@dataclass
class MetaIntentOutput:
    intent_score: float
    confidence: float
    expected_utility: float
    reason_codes: list[str]
    weights: dict[str, float]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_score": round(float(self.intent_score), 6),
            "confidence": round(float(self.confidence), 6),
            "expected_utility": round(float(self.expected_utility), 6),
            "reason_codes": list(self.reason_codes),
            "weights": {k: round(float(v), 6) for k, v in self.weights.items()},
            "diagnostics": self.diagnostics,
        }


@dataclass
class PolicyDecision:
    action: str
    safe_mode: bool
    rejections: list[str]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "safe_mode": bool(self.safe_mode),
            "rejections": list(self.rejections),
            "diagnostics": self.diagnostics,
        }


@dataclass
class CoreEngineResult:
    symbol: str
    timestamp: str
    score: float
    action: str
    confidence: float
    subscores: dict[str, float]
    model: dict[str, Any]
    diagnostics: dict[str, Any]
    weights: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "score": round(float(self.score), 6),
            "action": self.action,
            "confidence": round(float(self.confidence), 6),
            "subscores": {k: round(float(v), 6) for k, v in self.subscores.items()},
            "model": self.model,
            "diagnostics": self.diagnostics,
            "weights": {k: round(float(v), 6) for k, v in self.weights.items()},
        }
