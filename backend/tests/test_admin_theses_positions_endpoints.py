from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


class _Thesis:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, mode="json"):  # noqa: ARG002
        return dict(self._payload)


def _client():
    app = FastAPI()
    app.include_router(admin_routes.router)
    return TestClient(app)


def test_admin_theses_list_detail_and_updates(monkeypatch):
    admin_routes._ADMIN_THESIS_STATUS_OVERRIDES.clear()
    admin_routes._ADMIN_THESIS_CONVICTION_OVERRIDES.clear()
    admin_routes._ADMIN_THESIS_ALLOCATION_OVERRIDES.clear()

    thesis_id = "thesis-alpha"
    monkeypatch.setattr(
        admin_routes.firm_orchestrator,
        "_theses",
        {
            thesis_id: _Thesis(
                {
                    "thesis_id": thesis_id,
                    "run_id": "run-1",
                    "agent_id": "ceo",
                    "created_at": "2026-05-25T00:00:00Z",
                    "sleeve": "tactical",
                    "report_ids": ["report-1"],
                    "statement": "Long duration rates thesis",
                    "conviction": 0.62,
                }
            )
        },
    )
    monkeypatch.setattr(
        admin_routes.firm_orchestrator,
        "allocation_policy_status",
        lambda run_id=None: {"lines": [{"sleeve": "tactical", "allocated_usd": 500000.0}]},
    )
    monkeypatch.setattr(
        admin_routes.firm_orchestrator,
        "get_research_report",
        lambda report_id: {"report_id": report_id, "asset_universe": ["TLT"]},
    )
    monkeypatch.setattr(
        admin_routes.broker,
        "list_positions",
        lambda _: [
            {
                "symbol": "TLT",
                "qty": 100.0,
                "avg_price": 98.0,
                "market_value": 10100.0,
                "unrealized_pnl": 300.0,
            }
        ],
    )
    monkeypatch.setattr(admin_routes.FEED, "price", lambda symbol: 101.0 if symbol == "TLT" else 1.0)
    monkeypatch.setattr(admin_routes, "_record_runtime_control_event", lambda **kwargs: {})  # noqa: ARG005
    monkeypatch.setattr(admin_routes.broker, "submit_order", lambda **kwargs: {"status": "filled", **kwargs})  # noqa: ARG005

    client = _client()

    list_response = client.get("/api/admin/theses")
    assert list_response.status_code == 200
    theses = list_response.json()["theses"]
    assert len(theses) == 1
    assert theses[0]["thesis_id"] == thesis_id
    assert theses[0]["exit_signal"] == "HOLD"

    detail_response = client.get(f"/api/admin/theses/{thesis_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["holdings_count"] == 1
    assert len(detail["conviction_history"]) == 4

    conviction_update = client.put(
        f"/api/admin/theses/{thesis_id}/conviction",
        json={"conviction_pct": 70, "reason": "manual override"},
    )
    assert conviction_update.status_code == 200
    assert conviction_update.json()["conviction_pct"] == 70

    allocation_update = client.put(
        f"/api/admin/theses/{thesis_id}/allocation",
        json={"allocation_k": 420, "reason": "increase exposure"},
    )
    assert allocation_update.status_code == 200
    assert allocation_update.json()["allocation_usd"] == 420000.0

    close_response = client.put(
        f"/api/admin/theses/{thesis_id}/status",
        json={"status": "CLOSED", "reason": "manual close", "notes": "risk rotation"},
    )
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "CLOSED"
    assert close_response.json()["closed_positions"] == ["TLT"]


def test_admin_positions_list_and_detail(monkeypatch):
    monkeypatch.setattr(admin_routes.firm_orchestrator, "_theses", {})
    monkeypatch.setattr(
        admin_routes.broker,
        "list_positions",
        lambda _: [
            {
                "symbol": "AAPL",
                "qty": 10,
                "avg_price": 180.0,
                "market_value": 1850.0,
                "unrealized_pnl": 50.0,
                "asset_class": "equities",
            }
        ],
    )
    monkeypatch.setattr(admin_routes.FEED, "price", lambda symbol: 185.0 if symbol == "AAPL" else 1.0)

    client = _client()

    list_response = client.get("/api/admin/positions")
    assert list_response.status_code == 200
    positions = list_response.json()["positions"]
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"

    detail_response = client.get("/api/admin/positions/AAPL")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["symbol"] == "AAPL"
    assert detail["market_price"] == 185.0

