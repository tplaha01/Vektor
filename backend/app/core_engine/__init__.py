from __future__ import annotations

import hashlib
import json

from app.config import get_settings
from app.core_engine.contracts import CoreEngineResult
from app.core_engine.domain_models.fundamental_pack import run_fundamental_pack
from app.core_engine.domain_models.sentiment_pack import run_sentiment_pack
from app.core_engine.domain_models.technical_pack import run_technical_pack
from app.core_engine.feature_store import build_point_in_time_snapshot, rebind_snapshot_profile
from app.core_engine.policy.deterministic_policy import apply_deterministic_policy
from app.core_engine.routing import AUTO_PROFILE_NAME, resolve_profile_routing
from app.core_engine.stacking.meta_intent import run_meta_intent

_REQUIRED_MODEL_KEYS = ("technical_pack", "fundamental_pack", "sentiment_pack", "meta_intent", "policy")


def _contract_hash(*, feature_hash: str, profile_name: str, model_versions: dict[str, str]) -> str:
    payload = {
        "feature_hash": feature_hash,
        "profile": profile_name,
        "model_versions": {k: str(model_versions.get(k) or "") for k in sorted(model_versions)},
    }
    packed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def run_core_engine(symbol: str, profile: str | None = None) -> CoreEngineResult:
    settings = get_settings()
    requested_profile = str(profile).strip().lower() if profile is not None else AUTO_PROFILE_NAME
    if not requested_profile:
        requested_profile = AUTO_PROFILE_NAME
    base_profile = str(settings.CORE_ENGINE_PROFILE or "balanced").strip().lower() or "balanced"
    snapshot_profile = base_profile if requested_profile == AUTO_PROFILE_NAME else requested_profile

    snapshot = build_point_in_time_snapshot(symbol=symbol, profile=snapshot_profile)
    profile_routing = resolve_profile_routing(
        snapshot,
        requested_profile=requested_profile,
        base_profile=base_profile,
    )
    profile_name = str(profile_routing["active_profile"]).strip().lower()
    if snapshot.profile != profile_name:
        snapshot = rebind_snapshot_profile(snapshot, profile_name)

    technical = run_technical_pack(snapshot)
    fundamental = run_fundamental_pack(snapshot)
    sentiment = run_sentiment_pack(snapshot)
    meta = run_meta_intent(profile_name, technical, fundamental, sentiment)
    policy = apply_deterministic_policy(snapshot, meta)

    model_versions = dict(snapshot.model_versions)
    model_ready = bool(len(snapshot.history) >= 80 and all(str(model_versions.get(k) or "").strip() for k in _REQUIRED_MODEL_KEYS))
    contract_hash = _contract_hash(
        feature_hash=str(snapshot.lineage.get("feature_hash") or ""),
        profile_name=profile_name,
        model_versions=model_versions,
    )
    reason_codes = list(meta.reason_codes)
    if policy.rejections:
        reason_codes.extend(f"policy_{reason}" for reason in policy.rejections)
    reason_codes = sorted(set(reason_codes))

    diagnostics = {
        "signal_pipeline_only": True,
        "llm_signal_path": False,
        "market_pack_inference": True,
        "technical": technical.diagnostics,
        "fundamental": fundamental.diagnostics,
        "sentiment": sentiment.diagnostics,
        "domains": {
            "technical": technical.to_dict(),
            "fundamental": fundamental.to_dict(),
            "sentiment": sentiment.to_dict(),
        },
        "meta_intent": meta.to_dict(),
        "policy": policy.to_dict(),
        "freshness": snapshot.freshness.to_dict(),
        "lineage": dict(snapshot.lineage),
        "model_versions": model_versions,
        "profile": profile_name,
        "profile_routing": profile_routing,
        "reason_codes": reason_codes,
        "determinism": {
            "contract_hash": contract_hash,
            "feature_hash": snapshot.lineage.get("feature_hash"),
            "model_versions_pinned": bool(model_ready),
        },
    }
    model_meta = {
        "selected": model_versions.get("meta_intent", "meta-intent-v1"),
        "mandatory_ml": True,
        "ready": model_ready,
        "profile": profile_name,
    }
    subscores = {
        "technical": float(technical.alpha),
        "fundamental": float(fundamental.alpha),
        "sentiment": float(sentiment.alpha),
        "ml": float(meta.intent_score),
        "ml_alpha": float(meta.intent_score),
    }
    return CoreEngineResult(
        symbol=snapshot.symbol,
        timestamp=snapshot.as_of,
        score=float(meta.intent_score),
        action=policy.action,
        confidence=float(meta.confidence),
        subscores=subscores,
        model=model_meta,
        diagnostics=diagnostics,
        weights=dict(meta.weights),
    )
