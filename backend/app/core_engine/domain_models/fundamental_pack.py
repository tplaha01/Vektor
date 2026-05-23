from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.core_engine.contracts import DomainModelOutput, EngineInputSnapshot
from app.utils.common import clamp

_REQUIRED_RAW_FIELDS = ("revenue_growth", "gross_margin", "oper_margin", "debt_to_equity", "pe")
_FEATURE_ORDER = (
    "growth_quality",
    "margin_quality",
    "balance_sheet_strength",
    "earnings_yield",
    "momentum_20d",
    "volatility_penalty",
    "drawdown_penalty",
    "momentum_accel",
)
_MODEL_SPEC = {
    "family": "ridge_linear",
    "version": "fundamental-pack-ml-v2.0.0",
    "bias": 0.02,
    "weights": {
        "growth_quality": 0.30,
        "margin_quality": 0.22,
        "balance_sheet_strength": 0.17,
        "earnings_yield": 0.15,
        "momentum_20d": 0.12,
        "volatility_penalty": -0.08,
        "drawdown_penalty": -0.06,
        "momentum_accel": 0.05,
    },
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        pass
    return default


def _history_terms(closes: list[float]) -> dict[str, float]:
    if not closes:
        return {"ret_20d": 0.0, "vol_20d": 0.0, "drawdown_60d": 0.0, "momentum_accel": 0.0}

    ret_20 = 0.0
    vol_20 = 0.0
    drawdown_60 = 0.0
    accel = 0.0
    if len(closes) >= 21:
        prev = _safe_float(closes[-21], 0.0)
        now = _safe_float(closes[-1], 0.0)
        ret_20 = float(np.clip((now - prev) / (prev + 1e-9), -0.6, 0.6))
    if len(closes) >= 22:
        returns = np.diff(np.asarray(closes[-22:], dtype=float)) / np.maximum(np.asarray(closes[-22:-1], dtype=float), 1e-9)
        vol_20 = float(np.clip(np.std(returns), 0.0, 0.35))
        accel = float(np.clip(returns[-1] - returns[0], -0.4, 0.4))
    if len(closes) >= 60:
        tail = np.asarray(closes[-60:], dtype=float)
        peak = float(np.max(tail))
        trough = float(np.min(tail))
        drawdown_60 = float(np.clip((peak - trough) / max(peak, 1e-9), 0.0, 0.9))

    return {
        "ret_20d": ret_20,
        "vol_20d": vol_20,
        "drawdown_60d": drawdown_60,
        "momentum_accel": accel,
    }


def _build_feature_vector(snapshot: EngineInputSnapshot) -> tuple[dict[str, float], list[str], dict[str, float]]:
    fundamentals = snapshot.fundamentals if isinstance(snapshot.fundamentals, dict) else {}
    missing_fields = [name for name in _REQUIRED_RAW_FIELDS if name not in fundamentals]

    growth = _safe_float(fundamentals.get("revenue_growth"), 0.0)
    gross = _safe_float(fundamentals.get("gross_margin"), 0.0)
    oper = _safe_float(fundamentals.get("oper_margin"), 0.0)
    debt = _safe_float(fundamentals.get("debt_to_equity"), 1.5)
    pe = _safe_float(fundamentals.get("pe"), 30.0)

    closes = snapshot.history["close"].astype(float).tolist() if len(snapshot.history) else []
    history = _history_terms(closes)
    raw_inputs = {
        "revenue_growth": growth,
        "gross_margin": gross,
        "oper_margin": oper,
        "debt_to_equity": debt,
        "pe": pe,
        **history,
    }

    features = {
        "growth_quality": float(np.clip(growth / 0.25, -1.5, 1.5)),
        "margin_quality": float(np.clip(((gross + oper) * 0.5 - 0.12) / 0.32, -1.5, 1.5)),
        "balance_sheet_strength": float(np.clip(1.0 - (debt / 2.8), -1.5, 1.5)),
        "earnings_yield": float(np.clip((1.0 / max(pe, 1.0) - 0.04) / 0.08, -1.5, 1.5)),
        "momentum_20d": float(np.clip(history["ret_20d"] / 0.18, -1.5, 1.5)),
        "volatility_penalty": float(np.clip(history["vol_20d"] / 0.12, 0.0, 1.5)),
        "drawdown_penalty": float(np.clip(history["drawdown_60d"] / 0.35, 0.0, 1.5)),
        "momentum_accel": float(np.clip(history["momentum_accel"] / 0.08, -1.5, 1.5)),
    }
    return features, missing_fields, raw_inputs


def _infer_alpha(features: dict[str, float]) -> tuple[float, float, dict[str, float]]:
    score = float(_MODEL_SPEC["bias"])
    contributions: dict[str, float] = {}
    for name in _FEATURE_ORDER:
        weight = float(_MODEL_SPEC["weights"][name])
        contribution = weight * float(features[name])
        contributions[name] = contribution
        score += contribution
    alpha = clamp(float(np.tanh(score)))
    return alpha, score, contributions


def _confidence(features: dict[str, float], *, coverage_ratio: float) -> tuple[float, float]:
    boundary_penalty = float(
        np.mean([max(0.0, abs(float(features[name])) - 1.0) for name in _FEATURE_ORDER])
    )
    anomaly_score = float(np.clip(boundary_penalty / 0.8, 0.0, 1.0))
    confidence = float(np.clip(0.42 + 0.38 * coverage_ratio + 0.20 * (1.0 - anomaly_score), 0.05, 0.95))
    return confidence, anomaly_score


def run_fundamental_pack(snapshot: EngineInputSnapshot) -> DomainModelOutput:
    features, missing_fields, raw_inputs = _build_feature_vector(snapshot)
    coverage_ratio = float(np.clip(1.0 - (len(missing_fields) / float(len(_REQUIRED_RAW_FIELDS))), 0.0, 1.0))
    alpha, linear_score, contributions = _infer_alpha(features)
    alpha = float(alpha * max(0.25, coverage_ratio))

    confidence, anomaly_score = _confidence(features, coverage_ratio=coverage_ratio)
    uncertainty = float(np.clip(1.0 - confidence + 0.20 * anomaly_score, 0.05, 1.0))
    valuation_score = clamp(
        0.65 * features["earnings_yield"] + 0.35 * features["balance_sheet_strength"]
    )
    quality_score = clamp(
        0.55 * features["margin_quality"] + 0.45 * features["balance_sheet_strength"]
    )
    growth_score = clamp(
        0.70 * features["growth_quality"] + 0.30 * features["momentum_20d"]
    )
    authoritative = bool(coverage_ratio >= 0.60)

    return DomainModelOutput(
        name="fundamental",
        alpha=float(alpha),
        uncertainty=uncertainty,
        diagnostics={
            "inference_mode": "learned_fundamental_pack_linear",
            "legacy_rule_scoring": False,
            "authoritative_for_signal": authoritative,
            "model_family": _MODEL_SPEC["family"],
            "model_version": _MODEL_SPEC["version"],
            "alpha_confidence": confidence,
            "feature_order": list(_FEATURE_ORDER),
            "feature_vector": {k: float(features[k]) for k in _FEATURE_ORDER},
            "feature_contributions": contributions,
            "linear_score": float(linear_score),
            "coverage_ratio": coverage_ratio,
            "missing_fields": missing_fields,
            "raw_inputs": raw_inputs,
            "valuation_score": float(valuation_score),
            "quality_score": float(quality_score),
            "growth_score": float(growth_score),
            "anomaly_score": anomaly_score,
        },
    )
