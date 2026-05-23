import pytest

from app.strategies.hybrid import hybrid_signal

def test_signal_runs():
    out = hybrid_signal("AAPL")
    assert "score" in out and "action" in out
    assert -1.0 <= out["score"] <= 1.0
    assert "weights" in out and "ml_alpha" in out["weights"]
    assert "subscores" in out and "ml_alpha" in out["subscores"]
    assert "diagnostics" in out and "lineage" in out["diagnostics"]
