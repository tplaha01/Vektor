from __future__ import annotations

import numpy as np

from app.core_engine.contracts import DomainModelOutput, MetaIntentOutput
from app.core_engine.registry.model_registry import get_profile
from app.utils.common import clamp


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = float(sum(max(0.0, float(v)) for v in weights.values()))
    if total <= 0.0:
        return {"technical": 1.0 / 3.0, "fundamental": 1.0 / 3.0, "sentiment": 1.0 / 3.0}
    return {k: float(max(0.0, float(v)) / total) for k, v in weights.items()}


def run_meta_intent(
    profile_name: str,
    technical: DomainModelOutput,
    fundamental: DomainModelOutput,
    sentiment: DomainModelOutput,
) -> MetaIntentOutput:
    profile = get_profile(profile_name)
    weights = _normalize_weights(dict(profile.stack_weights))

    components = {
        "technical": technical.alpha,
        "fundamental": fundamental.alpha,
        "sentiment": sentiment.alpha,
    }
    uncertainty_components = {
        "technical": technical.uncertainty,
        "fundamental": fundamental.uncertainty,
        "sentiment": sentiment.uncertainty,
    }

    intent_score = clamp(sum(weights[k] * components[k] for k in weights))
    weighted_uncertainty = float(np.clip(sum(weights[k] * uncertainty_components[k] for k in weights), 0.0, 1.0))
    values = np.array([float(components[k]) for k in ("technical", "fundamental", "sentiment")], dtype=float)
    disagreement = float(np.clip(np.std(values), 0.0, 1.0))
    significant = [v for v in values if abs(float(v)) >= 0.10]
    if significant:
        sign_consensus = abs(float(np.sum(np.sign(significant)))) / float(len(significant))
    else:
        sign_consensus = 1.0
    uncertainty = float(np.clip(weighted_uncertainty + 0.30 * disagreement + 0.10 * (1.0 - sign_consensus), 0.0, 1.0))
    confidence = float(np.clip(1.0 - uncertainty + 0.16 * abs(intent_score), 0.0, 1.0))
    expected_utility = float(intent_score * confidence * (1.0 - 0.5 * uncertainty) * (1.0 - 0.35 * disagreement))

    top_signal = max(components.items(), key=lambda x: abs(float(x[1])))[0]
    reason_codes = [f"dominant_{top_signal}"]
    if confidence < profile.min_confidence:
        reason_codes.append("low_confidence")
    if abs(intent_score) < 0.15:
        reason_codes.append("weak_edge")
    if disagreement > 0.35:
        reason_codes.append("domain_disagreement")
    if expected_utility < 0.0:
        reason_codes.append("negative_expected_utility")

    return MetaIntentOutput(
        intent_score=float(intent_score),
        confidence=confidence,
        expected_utility=expected_utility,
        reason_codes=reason_codes,
        weights=weights,
        diagnostics={
            "components": components,
            "uncertainty_components": uncertainty_components,
            "profile": profile.name,
            "weights_normalized": weights,
            "sign_consensus": sign_consensus,
            "domain_disagreement": disagreement,
            "weighted_uncertainty": weighted_uncertainty,
            "aggregate_uncertainty": uncertainty,
        },
    )
