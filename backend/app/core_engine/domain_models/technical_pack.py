from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.core_engine.contracts import DomainModelOutput, EngineInputSnapshot
from app.ml.alpha_model import ensure_model, model_status, predict
from app.quant.regime import infer_market_regime
from app.utils.common import clamp


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        pass
    return default


def _market_pack_confidence(alpha: float, *, model_ready: bool, bars: int) -> float:
    magnitude = float(np.clip(abs(alpha), 0.0, 1.0))
    readiness = 1.0 if model_ready else 0.0
    history_term = float(np.clip((float(bars) - 80.0) / 240.0, 0.0, 1.0))
    return float(np.clip(0.20 + 0.45 * magnitude + 0.20 * readiness + 0.15 * history_term, 0.0, 1.0))


def run_market_pack_inference(snapshot: EngineInputSnapshot) -> DomainModelOutput:
    hist = snapshot.history
    if len(hist) < 80:
        return DomainModelOutput(
            name="technical",
            alpha=0.0,
            uncertainty=1.0,
            diagnostics={"reason": "insufficient_market_history", "bars": int(len(hist))},
        )

    regime = infer_market_regime(hist)
    ensure_model()
    learned_alpha = clamp(_safe_float(predict(hist)))
    model_meta = model_status()
    status = model_meta if isinstance(model_meta, dict) else {}
    ready = bool(status.get("ready"))

    confidence = _market_pack_confidence(learned_alpha, model_ready=ready, bars=len(hist))
    uncertainty = float(np.clip(1.0 - confidence, 0.05, 1.0))
    diagnostics = {
        "inference_mode": "learned_market_pack" if ready else "learned_market_pack_fallback",
        "legacy_indicator_scoring": False,
        "authoritative_for_signal": bool(ready),
        "model_ready": ready,
        "model_training": bool(status.get("training")),
        "model_features": int(status.get("features") or 0),
        "model_artifact_path": status.get("path"),
        "confidence": confidence,
        "regime": regime.regime,
        "regime_edge": _safe_float(regime.edge),
        "regime_confidence": _safe_float(regime.confidence),
        "atr_pct": _safe_float(regime.atr_pct),
        "volume_ratio": _safe_float(regime.volume_ratio),
        "realised_vol_20d": _safe_float(regime.realised_vol_20d),
    }
    if not ready:
        diagnostics["reason"] = "market_pack_model_not_ready"

    return DomainModelOutput(
        name="technical",
        alpha=learned_alpha,
        uncertainty=uncertainty,
        diagnostics=diagnostics,
    )


def run_technical_pack(snapshot: EngineInputSnapshot) -> DomainModelOutput:
    return run_market_pack_inference(snapshot)
