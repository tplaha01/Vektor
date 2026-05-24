from __future__ import annotations

from typing import Any


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_number(value: object) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _clamp01(value: object, fallback: float = 0.0) -> float:
    return max(0.0, min(1.0, _safe_float(value, fallback)))


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def build_decision_scoring_from_signal(
    *,
    symbol: str,
    asset_class: str,
    engine_signal: dict[str, Any],
    strategy_family: str = "deterministic_ml_firm_engine",
) -> dict[str, Any]:
    diagnostics = _as_dict(engine_signal.get("diagnostics"))
    technical_diag = _as_dict(diagnostics.get("technical"))
    sentiment_diag = _as_dict(diagnostics.get("sentiment"))
    meta_intent = _as_dict(diagnostics.get("meta_intent"))
    meta_diag = _as_dict(meta_intent.get("diagnostics"))
    policy_diag = _as_dict(diagnostics.get("policy"))
    subscores = _as_dict(engine_signal.get("subscores"))
    model = _as_dict(engine_signal.get("model"))

    score = _safe_float(engine_signal.get("score"))
    confidence = _clamp01(engine_signal.get("confidence"), fallback=min(1.0, abs(score)))
    expected_utility = _safe_float(meta_intent.get("expected_utility"))
    direction = "long_bias" if score >= 0.0 else "short_bias"
    model_name = str(model.get("selected") or "deterministic_ml").strip() or "deterministic_ml"

    regime_alignment = _clamp01(
        meta_diag.get("sign_consensus"),
        fallback=_clamp01(0.5 + (_safe_float(technical_diag.get("regime_edge")) / 2.0)),
    )
    liquidity_score = _clamp01(technical_diag.get("volume_ratio"))
    news_intensity_count = int(max(0.0, _safe_float(sentiment_diag.get("headline_count"))))
    directional_probability_up = _clamp01(0.5 + score / 2.0)
    aggregate_uncertainty = _clamp01(meta_diag.get("aggregate_uncertainty"), fallback=max(0.0, 1.0 - confidence))
    domain_disagreement = _clamp01(meta_diag.get("domain_disagreement"))

    return {
        "symbol": str(symbol or "").upper().strip(),
        "asset_class": str(asset_class or "").strip().lower(),
        "strategy_family": str(strategy_family or "deterministic_ml_firm_engine").strip() or "deterministic_ml_firm_engine",
        "score": score,
        "confidence": confidence,
        "direction": direction,
        "horizon": "swing",
        "reason_codes": _as_list(meta_intent.get("reason_codes")) or _as_list(diagnostics.get("reason_codes")),
        "math_summary": (
            f"deterministic_ml={score:.4f} confidence={confidence:.4f} "
            f"expected_utility={expected_utility:.4f} model={model_name}"
        ),
        "metrics": {
            "directional_probability_up": directional_probability_up,
            "technical_confidence": _clamp01(technical_diag.get("confidence")),
            "ml_confidence": confidence,
            "sentiment_normalized": _safe_float(subscores.get("sentiment")),
            "liquidity_score": liquidity_score,
            "volatility_score": _safe_float(technical_diag.get("atr_pct")),
            "news_intensity_count": news_intensity_count,
            "regime_alignment": regime_alignment,
            "expected_utility": expected_utility,
            "aggregate_uncertainty": aggregate_uncertainty,
            "domain_disagreement": domain_disagreement,
            "model_name": model_name,
            "policy_safe_mode": bool(policy_diag.get("safe_mode", False)),
            "ml_mandatory": True,
        },
    }


def resolve_decision_scoring(
    *,
    metadata: dict[str, object] | None,
    symbol: str,
    asset_class: str,
) -> dict[str, Any]:
    meta = _as_dict(metadata)
    existing = dict(meta.get("decision_scoring")) if isinstance(meta.get("decision_scoring"), dict) else {}
    strategy_family = str(
        existing.get("strategy_family")
        or meta.get("strategy_family")
        or "deterministic_ml_firm_engine"
    ).strip() or "deterministic_ml_firm_engine"
    engine_signal = _as_dict(meta.get("deterministic_ml_signal"))

    derived: dict[str, Any] = {}
    if engine_signal:
        derived = build_decision_scoring_from_signal(
            symbol=symbol,
            asset_class=asset_class,
            engine_signal=engine_signal,
            strategy_family=strategy_family,
        )

    if not existing:
        return derived
    if not derived:
        return existing

    merged = dict(existing)
    if not _is_number(merged.get("score")):
        merged["score"] = derived.get("score")
    if not _is_number(merged.get("confidence")):
        merged["confidence"] = derived.get("confidence")
    if not str(merged.get("direction") or "").strip():
        merged["direction"] = derived.get("direction")
    if not str(merged.get("strategy_family") or "").strip():
        merged["strategy_family"] = derived.get("strategy_family")
    if not str(merged.get("asset_class") or "").strip():
        merged["asset_class"] = derived.get("asset_class")
    if not str(merged.get("symbol") or "").strip():
        merged["symbol"] = derived.get("symbol")
    if not str(merged.get("math_summary") or "").strip():
        merged["math_summary"] = derived.get("math_summary")
    if not isinstance(merged.get("reason_codes"), list):
        merged["reason_codes"] = list(derived.get("reason_codes") or [])

    existing_metrics = merged.get("metrics") if isinstance(merged.get("metrics"), dict) else {}
    derived_metrics = _as_dict(derived.get("metrics"))
    merged_metrics = dict(existing_metrics)
    for key, value in derived_metrics.items():
        if key not in merged_metrics:
            merged_metrics[key] = value
    if merged_metrics:
        merged["metrics"] = merged_metrics

    return merged
