from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MarketRegimeSnapshot:
    regime: str
    direction: str
    confidence: float
    edge: float
    trend_score: float
    breakout_score: float
    mean_reversion_score: float
    volatility_score: float
    liquidity_score: float
    adx: float | None = None
    atr_pct: float | None = None
    realised_vol_20d: float | None = None
    rsi: float | None = None
    volume_ratio: float | None = None
    notes: tuple[str, ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "direction": self.direction,
            "confidence": round(float(self.confidence), 4),
            "edge": round(float(self.edge), 4),
            "trend_score": round(float(self.trend_score), 4),
            "breakout_score": round(float(self.breakout_score), 4),
            "mean_reversion_score": round(float(self.mean_reversion_score), 4),
            "volatility_score": round(float(self.volatility_score), 4),
            "liquidity_score": round(float(self.liquidity_score), 4),
            "adx": None if self.adx is None else round(float(self.adx), 4),
            "atr_pct": None if self.atr_pct is None else round(float(self.atr_pct), 6),
            "realised_vol_20d": None if self.realised_vol_20d is None else round(float(self.realised_vol_20d), 6),
            "rsi": None if self.rsi is None else round(float(self.rsi), 4),
            "volume_ratio": None if self.volume_ratio is None else round(float(self.volume_ratio), 4),
            "notes": list(self.notes),
            "metrics": {key: round(float(value), 6) for key, value in self.metrics.items()},
        }


@dataclass(frozen=True)
class PortfolioRegimeSnapshot:
    macro_risk_level: str
    risk_score: float
    symbol_exposure_ratio: float
    correlated_group_exposure_ratio: float
    asset_class_usage_ratio: float
    cash_reserve_ratio: float
    leverage_ratio: float
    notes: tuple[str, ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "macro_risk_level": self.macro_risk_level,
            "risk_score": round(float(self.risk_score), 4),
            "symbol_exposure_ratio": round(float(self.symbol_exposure_ratio), 4),
            "correlated_group_exposure_ratio": round(float(self.correlated_group_exposure_ratio), 4),
            "asset_class_usage_ratio": round(float(self.asset_class_usage_ratio), 4),
            "cash_reserve_ratio": round(float(self.cash_reserve_ratio), 4),
            "leverage_ratio": round(float(self.leverage_ratio), 4),
            "notes": list(self.notes),
            "metrics": {key: round(float(value), 6) for key, value in self.metrics.items()},
        }
