from __future__ import annotations

from app.utils.common import clamp


def fundamental_score(fundamentals: dict[str, float]) -> float:
    score = 0.0
    score += min(float(fundamentals.get("revenue_growth", 0.0)), 0.3) * (1 / 0.3) * 0.35
    score += min(float(fundamentals.get("gross_margin", 0.0)), 0.7) * (1 / 0.7) * 0.35
    score += min(float(fundamentals.get("oper_margin", 0.0)), 0.5) * (1 / 0.5) * 0.30
    score -= min(float(fundamentals.get("debt_to_equity", 1.0)) / 3.0, 1.0) * 0.25
    score -= min(float(fundamentals.get("pe", 20.0)) / 60.0, 1.0) * 0.25
    return clamp(score)
