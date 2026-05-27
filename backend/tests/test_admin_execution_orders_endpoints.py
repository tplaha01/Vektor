from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


def _client():
    app = FastAPI()
    app.include_router(admin_routes.router)
    return TestClient(app)


def test_admin_orders_list_detail_quality_tape_and_settings(monkeypatch):
    admin_routes._ADMIN_EXECUTION_PRIORITY.update(
        {"priority": "QUALITY", "reason": "default_execution_priority", "updated_at": None}
    )
    order = {
        "id": "ord-1",
        "symbol": "AAPL",
        "side": "buy",
        "qty": 5.0,
        "avg_price": 101.0,
        "price": 101.0,
        "status": "filled",
        "created_at": "2026-05-25T15:30:00Z",
        "asset_class": "equities",
        "instrument_type": "equity",
        "contract_multiplier": 1.0,
        "metadata": {
            "reference_price": 100.0,
            "requested_order_type": "MARKET",
            "requested_time_in_force": "IOC",
            "notes": "rebalance into strength",
            "thesis_id": "thesis-1",
        },
    }
    monkeypatch.setattr(admin_routes.broker, "list_orders", lambda: [order])
    monkeypatch.setattr(
        admin_routes,
        "_admin_order_context_map",
        lambda limit=250: {
            "ord-1": {
                "decision_id": "decision-1",
                "run_id": "run-1",
                "agent_id": "admin_operator",
                "thesis_id": "thesis-1",
                "approval_status": "auto",
                "signal_conviction_pct": 72.0,
                "audit_timeline_path": "/api/admin/audit/orders/ord-1/timeline",
            }
        },
    )
    monkeypatch.setattr(
        admin_routes.firm_orchestrator,
        "audit_timeline_for_order",
        lambda order_id: [
            {
                "source": "decision_ledger",
                "event_id": "evt-1",
                "event_type": "paper.order.executed",
                "timestamp": "2026-05-25T15:30:00Z",
                "payload": {"order_id": order_id, "symbol": "AAPL"},
            }
        ],
    )

    client = _client()

    list_response = client.get("/api/admin/orders?status=FILLED&time=ALL")
    assert list_response.status_code == 200
    rows = list_response.json()["orders"]
    assert len(rows) == 1
    assert rows[0]["order_id"] == "ord-1"
    assert rows[0]["slippage_bps"] == 100.0

    detail_response = client.get("/api/admin/orders/ord-1")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["execution_context"]["thesis_id"] == "thesis-1"
    assert detail["execution_quality"]["interpretation"] == "Unfavorable"

    fills_response = client.get("/api/admin/orders/ord-1/fills")
    assert fills_response.status_code == 200
    assert fills_response.json()["total_quantity"] == 5.0

    quality_response = client.get("/api/admin/orders/ord-1/execution_quality")
    assert quality_response.status_code == 200
    assert quality_response.json()["slippage_bps"] == 100.0

    tape_response = client.get("/api/admin/orders/tape?days=90")
    assert tape_response.status_code == 200
    assert tape_response.json()["rows"][0]["order_id"] == "ord-1"

    broker_response = client.get("/api/admin/broker/config")
    assert broker_response.status_code == 200
    assert broker_response.json()["broker"] == "Paper broker"

    priority_response = client.get("/api/admin/execution/priority")
    assert priority_response.status_code == 200
    assert priority_response.json()["priority"] == "QUALITY"


def test_admin_order_validate_submit_cancel_and_priority_update(monkeypatch):
    admin_routes._ADMIN_EXECUTION_PRIORITY.update(
        {"priority": "QUALITY", "reason": "default_execution_priority", "updated_at": None}
    )
    pending_order = {
        "id": "pending-1",
        "symbol": "MSFT",
        "side": "buy",
        "qty": 10.0,
        "avg_price": 99.5,
        "price": 99.5,
        "status": "pending",
        "created_at": "2026-05-25T15:35:00Z",
        "asset_class": "equities",
        "instrument_type": "equity",
        "contract_multiplier": 1.0,
        "metadata": {},
    }
    monkeypatch.setattr(admin_routes.FEED, "price", lambda symbol: 100.0 if symbol else 0.0)
    monkeypatch.setattr(
        admin_routes.broker,
        "list_positions",
        lambda _: [
            {"symbol": "AAPL", "qty": 50, "market_value": 5000.0, "asset_class": "equities"},
            {"symbol": "QQQ", "qty": 20, "market_value": 8000.0, "asset_class": "equities"},
        ],
    )
    monkeypatch.setattr(admin_routes.broker, "get_portfolio_value", lambda _: 100000.0)
    monkeypatch.setattr(admin_routes.broker, "get_cash", lambda: 20000.0)
    monkeypatch.setattr(admin_routes.broker, "order_history", [pending_order])
    monkeypatch.setattr(admin_routes.broker, "list_orders", lambda: list(reversed(admin_routes.broker.order_history)))
    monkeypatch.setattr(admin_routes.risk, "pre_trade_check", lambda *args, **kwargs: (True, ""))  # noqa: ARG005
    monkeypatch.setattr(admin_routes.storage_db, "save_order", lambda order: None)
    captured = {}

    def _fake_execute_manual_paper_order(**kwargs):
        captured.update(kwargs)
        return {
            "approved": True,
            "status": "executed",
            "run_id": kwargs["run_id"],
            "decision_id": kwargs["decision_id"],
            "risk_id": "risk-1",
            "intent_id": "intent-1",
            "order": {
                "id": "exec-1",
                "symbol": kwargs["symbol"],
                "side": kwargs["side"],
                "quantity": kwargs["quantity"],
                "avg_price": 100.5,
                "price": 100.5,
                "status": "filled",
                "created_at": "2026-05-25T15:40:00Z",
                "asset_class": "equities",
                "instrument_type": "equity",
                "contract_multiplier": 1.0,
                "metadata": dict(kwargs["metadata"]),
            },
        }

    monkeypatch.setattr(admin_routes.firm_orchestrator, "execute_manual_paper_order", _fake_execute_manual_paper_order)
    monkeypatch.setattr(
        admin_routes,
        "_admin_order_context_map",
        lambda limit=250: {
            "exec-1": {
                "decision_id": "decision-1",
                "run_id": "run-1",
                "agent_id": "admin_operator",
                "thesis_id": "thesis-2",
                "approval_status": "auto",
                "signal_conviction_pct": 68.0,
                "audit_timeline_path": "/api/admin/audit/orders/exec-1/timeline",
            }
        },
    )

    client = _client()

    payload = {
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 1500,
        "order_type": "MARKET",
        "time_in_force": "IOC",
        "reason": "manual macro override",
        "thesis_id": "thesis-2",
        "override": False,
    }
    validate_response = client.post("/api/admin/orders/validate", json=payload)
    assert validate_response.status_code == 200
    assert validate_response.json()["requires_override"] is True

    blocked_response = client.post("/api/admin/orders", json=payload)
    assert blocked_response.status_code == 200
    assert blocked_response.json()["approved"] is False
    assert blocked_response.json()["error"] == "approval_override_required"

    submit_response = client.post("/api/admin/orders", json={**payload, "override": True})
    assert submit_response.status_code == 200
    submit_body = submit_response.json()
    assert submit_body["approved"] is True
    assert submit_body["order"]["order_id"] == "exec-1"
    assert captured["metadata"]["override_requested"] is True
    assert captured["metadata"]["thesis_id"] == "thesis-2"

    cancel_response = client.put(
        "/api/admin/orders/pending-1",
        json={"status": "CANCELLED", "reason": "desk pull"},
    )
    assert cancel_response.status_code == 200
    assert pending_order["status"] == "cancelled"

    priority_response = client.put(
        "/api/admin/execution/priority",
        json={"priority": "SPEED", "reason": "urgent macro event"},
    )
    assert priority_response.status_code == 200
    assert priority_response.json()["priority"] == "SPEED"
