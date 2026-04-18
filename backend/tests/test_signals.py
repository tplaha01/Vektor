import pytest

from app.strategies.hybrid import hybrid_signal

def test_signal_runs():
    out = hybrid_signal("AAPL")
    assert "score" in out and "action" in out
    assert -1.0 <= out["score"] <= 1.0
