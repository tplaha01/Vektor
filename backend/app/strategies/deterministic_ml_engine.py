from __future__ import annotations

from app.core_engine import run_core_engine
from app.core_engine.contracts import CoreEngineResult

# Backward-compatible alias for older imports.
EngineResult = CoreEngineResult


def deterministic_signal(symbol: str) -> EngineResult:
    """
    Legacy entrypoint kept for API compatibility.
    All deterministic signal generation is delegated to the core engine pipeline.
    """
    return run_core_engine(symbol)
