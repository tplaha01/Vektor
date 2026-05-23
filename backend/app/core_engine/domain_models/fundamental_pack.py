from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.core_engine.contracts import DomainModelOutput, EngineInputSnapshot
from app.utils.common import clamp


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        pass
    return default


def _domain_weights(symbol: str) -> dict[str, float]:
    sym = str(symbol or "").upper().strip()
    tech = {"AAPL", "MSFT", "NVDA", "AMD", "AMZN", "GOOGL", "META", "TSLA"}
    finance = {"JPM", "BAC", "GS", "MS", "WFC", "C"}
    energy = {"XOM", "CVX", "COP", "EOG", "SLB", "USO", "UNG"}
    if sym in tech:
        return {"growth": 0.42, "margin": 0.32, "leverage": 0.16, "valuation": 0.10}
    if sym in finance:
        return {"growth": 0.28, "margin": 0.22, "leverage": 0.30, "valuation": 0.20}
    if sym in energy:
        return {"growth": 0.24, "margin": 0.28, "leverage": 0.28, "valuation": 0.20}
    return {"growth": 0.34, "margin": 0.30, "leverage": 0.20, "valuation": 0.16}


def _projection(fundamentals: dict[str, Any], closes: list[float]) -> tuple[dict[str, float], float]:
    growth = _safe_float(fundamentals.get("revenue_growth"), 0.05)
    gross = _safe_float(fundamentals.get("gross_margin"), 0.35)
    oper = _safe_float(fundamentals.get("oper_margin"), 0.18)
    debt = _safe_float(fundamentals.get("debt_to_equity"), 1.0)
    pe = _safe_float(fundamentals.get("pe"), 22.0)

    drift = 0.0
    if len(closes) >= 21:
        prev = _safe_float(closes[-21], 0.0)
        now = _safe_float(closes[-1], 0.0)
        ret_20 = (now - prev) / (prev + 1e-9)
        drift = float(np.clip(ret_20 * 0.35, -0.08, 0.08))

    projected = {
        "revenue_growth_fwd": float(np.clip(growth + drift, -0.2, 0.8)),
        "gross_margin_fwd": float(np.clip(gross + drift * 0.2, 0.05, 0.85)),
        "oper_margin_fwd": float(np.clip(oper + drift * 0.25, -0.2, 0.6)),
        "debt_to_equity_fwd": float(np.clip(debt - drift * 0.6, 0.0, 6.0)),
        "pe_fwd": float(np.clip(pe - drift * 40.0, 2.0, 120.0)),
    }
    projection_confidence = float(np.clip(0.55 + abs(drift) * 2.0, 0.55, 0.9))
    return projected, projection_confidence


def run_fundamental_pack(snapshot: EngineInputSnapshot) -> DomainModelOutput:
    closes = snapshot.history["close"].astype(float).tolist() if len(snapshot.history) else []
    projected, projection_conf = _projection(snapshot.fundamentals, closes)
    weights = _domain_weights(snapshot.symbol)

    growth_term = float(np.clip(projected["revenue_growth_fwd"] / 0.25, -1.0, 1.0))
    margin = (projected["gross_margin_fwd"] + projected["oper_margin_fwd"]) / 2.0
    margin_term = float(np.clip((margin - 0.2) / 0.35, -1.0, 1.0))
    leverage_term = float(np.clip(1.0 - (projected["debt_to_equity_fwd"] / 2.5), -1.0, 1.0))
    valuation_term = float(np.clip(1.0 - (projected["pe_fwd"] / 35.0), -1.0, 1.0))

    alpha = clamp(
        weights["growth"] * growth_term
        + weights["margin"] * margin_term
        + weights["leverage"] * leverage_term
        + weights["valuation"] * valuation_term
    )
    uncertainty = float(np.clip(1.0 - projection_conf, 0.05, 0.95))

    return DomainModelOutput(
        name="fundamental",
        alpha=alpha,
        uncertainty=uncertainty,
        diagnostics={
            "projection": projected,
            "projection_confidence": projection_conf,
            "weights": weights,
            "terms": {
                "growth": growth_term,
                "margin": margin_term,
                "leverage": leverage_term,
                "valuation": valuation_term,
            },
        },
    )
