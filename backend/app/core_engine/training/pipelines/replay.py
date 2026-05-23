from __future__ import annotations

from typing import Any


def deterministic_replay(symbols: list[str], profile: str = "balanced") -> list[dict[str, Any]]:
    # Imported lazily to avoid circular imports from core_engine.__init__.
    from app.core_engine import run_core_engine

    results: list[dict[str, Any]] = []
    for symbol in symbols:
        out = run_core_engine(symbol, profile=profile).to_dict()
        results.append(
            {
                "symbol": out["symbol"],
                "timestamp": out["timestamp"],
                "score": out["score"],
                "confidence": out["confidence"],
                "action": out["action"],
                "run_id": out["diagnostics"]["lineage"]["run_id"],
                "decision_id": out["diagnostics"]["lineage"]["decision_id"],
            }
        )
    return results
