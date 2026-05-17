from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AssetClass = Literal["equities", "options", "forex", "crypto", "commodities", "macro", "unknown"]
UseCase = Literal["execution", "risk", "alpha", "research", "monitoring"]


@dataclass(frozen=True)
class QualityResult:
    dataset: str
    symbol: str | None
    provider: str
    score: float
    flags: tuple[str, ...] = ()
    severity: str = "ok"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureVector:
    symbol: str
    asset_class: AssetClass
    use_case: UseCase
    as_of: str
    features: dict[str, Any]
    score: float
    category: str
    source_snapshot_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
