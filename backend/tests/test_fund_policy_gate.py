from app.fund.execution_adapter import ExecutionIntent
from app.fund.policy_gate import PolicyGate, PolicyLimits


def _base_intent(**overrides):
    payload = {
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 10.0,
        "approved": True,
        "decision_id": "decision-1",
        "risk_id": "risk-1",
        "run_id": "run-1",
        "agent_id": "trader-1",
        "broker_mode": "paper",
        "price": 100.0,
        "metadata": {"available_cash": 100_000.0, "sleeve": "tactical"},
    }
    payload.update(overrides)
    return ExecutionIntent(**payload)


def test_policy_gate_allows_valid_intent():
    gate = PolicyGate()
    approved, reasons = gate.evaluate(_base_intent(), positions=[], equity=100_000.0)
    assert approved is True
    assert reasons == []


def test_policy_gate_blocks_live_trading_and_large_notional():
    gate = PolicyGate(limits=PolicyLimits(max_order_notional_usd=25_000.0))
    approved, reasons = gate.evaluate(
        _base_intent(broker_mode="live", quantity=500.0, price=100.0),
        positions=[],
        equity=100_000.0,
    )
    assert approved is False
    assert "live_trading_disabled" in reasons
    assert "order_notional_limit_exceeded" in reasons


def test_policy_gate_blocks_when_available_cash_is_zero():
    gate = PolicyGate()
    approved, reasons = gate.evaluate(
        _base_intent(metadata={"available_cash": 0.0, "sleeve": "tactical"}),
        positions=[],
        equity=100_000.0,
    )
    assert approved is False
    assert "insufficient_cash" in reasons


def test_policy_gate_allows_sell_that_reduces_exposure_even_when_notional_is_large():
    gate = PolicyGate()
    approved, reasons = gate.evaluate(
        _base_intent(
            side="sell",
            quantity=50.0,  # $5,000 notional (50% of equity below)
            price=100.0,
            metadata={"available_cash": 0.0, "sleeve": "tactical"},
        ),
        positions=[{"symbol": "AAPL", "qty": 100.0, "market_price": 10.0, "market_value": 1_000.0}],
        equity=10_000.0,
    )
    assert approved is True
    assert "single_position_notional_limit_exceeded" not in reasons
