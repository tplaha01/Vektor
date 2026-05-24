from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.main as main
import app.strategies.auto_trader as auto_trader_module
from app.models import OrderIn


class _StubFeed:
    def price(self, symbol: str) -> float:
        _ = symbol
        return 100.0


class _StubGuard:
    def halted(self) -> bool:
        return False

    def halt_reason(self) -> str | None:
        return None


class _StubManager:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def broadcast(self, payload: dict) -> None:
        self.payloads.append(dict(payload))


class _StubBroker:
    def list_positions(self, price_lookup):  # noqa: ARG002
        return []


class _StubRisk:
    def __init__(self, *, approved: bool = True, reason: str = "approved") -> None:
        self.approved = approved
        self.reason = reason
        self.registered: list[tuple[str, float, float, str]] = []

    def pre_trade_check(self, symbol: str, side: str, shares: float, price: float, positions: list[dict]):
        _ = (symbol, side, shares, price, positions)
        return self.approved, self.reason

    def register_entry(self, symbol: str, price: float, atr: float, side: str) -> None:
        self.registered.append((symbol, float(price), float(atr), side))


class _StubOrchestrator:
    def __init__(self, response: dict) -> None:
        self.response = dict(response)
        self.calls: list[dict] = []

    def execute_manual_paper_order(self, **kwargs):
        self.calls.append(dict(kwargs))
        return dict(self.response)


@pytest.mark.anyio
async def test_place_order_delegates_to_orchestrator_and_preserves_manual_response_shape(monkeypatch):
    orchestrator = _StubOrchestrator(
        response={
            "approved": True,
            "status": "executed",
            "run_id": "run-1",
            "decision_id": "decision-1",
            "risk_id": "risk-1",
            "intent_id": "intent-1",
            "reasons": [],
            "order": {
                "id": "order-1",
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 2.0,
                "avg_price": 100.0,
                "status": "filled",
                "created_at": "2026-05-23T00:00:00Z",
            },
        }
    )
    risk = _StubRisk(approved=True)
    manager = _StubManager()

    monkeypatch.setattr(main, "FEED", _StubFeed())
    monkeypatch.setattr(main, "broker", _StubBroker())
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "risk", risk)
    monkeypatch.setattr(main, "data_integrity_guard", _StubGuard())
    monkeypatch.setattr(main, "firm_orchestrator", orchestrator)
    monkeypatch.setattr(auto_trader_module, "_current_atr", lambda _symbol: 2.5)

    req = SimpleNamespace(headers={})
    out = await main.place_order(OrderIn(symbol="aapl", side="buy", quantity=2.0), req)

    assert out == {
        "id": "order-1",
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 2.0,
        "price": 100.0,
        "timestamp": "2026-05-23T00:00:00Z",
        "status": "filled",
        "approved": True,
        "run_id": "run-1",
        "decision_id": "decision-1",
        "risk_id": "risk-1",
        "intent_id": "intent-1",
    }
    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0]["symbol"] == "AAPL"
    assert orchestrator.calls[0]["side"] == "buy"
    assert orchestrator.calls[0]["external_blocked_reasons"] == []
    assert risk.registered == [("AAPL", 100.0, 2.5, "long")]
    assert len(manager.payloads) == 1
    assert manager.payloads[0]["type"] == "positions_update"


@pytest.mark.anyio
async def test_place_order_preserves_blocked_reason_payload_from_orchestrator(monkeypatch):
    orchestrator = _StubOrchestrator(
        response={
            "approved": False,
            "status": "blocked",
            "error": "ml_score_below_threshold",
            "run_id": "run-2",
            "decision_id": "decision-2",
            "risk_id": "risk-2",
            "intent_id": "intent-2",
            "reasons": ["ml_score_below_threshold", "risk_engine:limit"],
        }
    )
    risk = _StubRisk(approved=False, reason="limit")

    monkeypatch.setattr(main, "FEED", _StubFeed())
    monkeypatch.setattr(main, "broker", _StubBroker())
    monkeypatch.setattr(main, "manager", _StubManager())
    monkeypatch.setattr(main, "risk", risk)
    monkeypatch.setattr(main, "data_integrity_guard", _StubGuard())
    monkeypatch.setattr(main, "firm_orchestrator", orchestrator)

    req = SimpleNamespace(headers={})
    out = await main.place_order(OrderIn(symbol="aapl", side="buy", quantity=2.0), req)

    assert out == {
        "error": "ml_score_below_threshold",
        "approved": False,
        "run_id": "run-2",
        "decision_id": "decision-2",
        "risk_id": "risk-2",
        "intent_id": "intent-2",
        "reasons": ["ml_score_below_threshold", "risk_engine:limit"],
    }
    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0]["external_blocked_reasons"] == ["risk_engine:limit"]
