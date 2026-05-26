from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


def _client():
    app = FastAPI()
    app.include_router(admin_routes.router)
    return TestClient(app)


def test_admin_risk_metric_endpoints(monkeypatch):
    monkeypatch.setattr(
        admin_routes.storage_db,
        "load_performance_snapshots",
        lambda limit=60: [
            {"recorded_at": "2026-05-20T00:00:00Z", "equity": 100000.0},
            {"recorded_at": "2026-05-21T00:00:00Z", "equity": 101500.0},
            {"recorded_at": "2026-05-22T00:00:00Z", "equity": 100500.0},
            {"recorded_at": "2026-05-23T00:00:00Z", "equity": 102000.0},
        ],
    )
    monkeypatch.setattr(
        admin_routes.broker,
        "list_positions",
        lambda _: [
            {"symbol": "AAPL", "qty": 20, "market_value": 4000.0, "asset_class": "equities"},
            {"symbol": "JPM", "qty": 10, "market_value": 2500.0, "asset_class": "equities"},
        ],
    )
    monkeypatch.setattr(admin_routes.broker, "get_portfolio_value", lambda _: 105000.0)
    monkeypatch.setattr(admin_routes.FEED, "price", lambda symbol: {"AAPL": 200.0, "JPM": 250.0}.get(symbol, 100.0))
    monkeypatch.setattr(
        admin_routes.risk,
        "status",
        lambda: {
            "equity": 105000.0,
            "drawdown_breaker": {
                "current_drawdown": 0.032,
                "max_drawdown_threshold": 0.15,
                "halted": False,
            },
        },
    )
    monkeypatch.setattr(admin_routes.risk, "var_guard", SimpleNamespace(max_var_pct=0.05))
    monkeypatch.setattr(
        admin_routes.performance_tracker,
        "summary",
        lambda: {"track_record": {"sharpe_ratio": 1.24}},
    )

    client = _client()

    var_response = client.get("/api/admin/risk/var")
    cvar_response = client.get("/api/admin/risk/cvar")
    drawdown_response = client.get("/api/admin/risk/drawdown")
    leverage_response = client.get("/api/admin/risk/leverage")
    sharpe_response = client.get("/api/admin/risk/sharpe")

    assert var_response.status_code == 200
    assert var_response.json()["max_allowed_usd"] == 5250.0

    assert cvar_response.status_code == 200
    assert cvar_response.json()["max_allowed_pct"] == 8.0

    assert drawdown_response.status_code == 200
    assert drawdown_response.json()["current_drawdown_pct"] == 3.2

    assert leverage_response.status_code == 200
    assert leverage_response.json()["max_allowed_leverage"] == 1.5

    assert sharpe_response.status_code == 200
    assert sharpe_response.json()["rolling_30d"] == 1.24


def test_admin_policy_endpoints_and_threshold_update(monkeypatch):
    admin_routes._ADMIN_POLICY_THRESHOLD_OVERRIDES.clear()
    monkeypatch.setattr(
        admin_routes.broker,
        "list_positions",
        lambda _: [
            {"symbol": "AAPL", "qty": 20, "market_value": 4000.0, "asset_class": "equities"},
            {"symbol": "JPM", "qty": 10, "market_value": 2500.0, "asset_class": "equities"},
            {"symbol": "TLT", "qty": 15, "market_value": 3000.0, "asset_class": "equities"},
        ],
    )
    monkeypatch.setattr(admin_routes.broker, "get_portfolio_value", lambda _: 100000.0)
    monkeypatch.setattr(admin_routes.FEED, "price", lambda symbol: 100.0)
    monkeypatch.setattr(
        admin_routes.firm_orchestrator,
        "allocation_policy_status",
        lambda run_id=None: {
            "policy": {
                "constraints": {
                    "min_cash_reserve_pct": 0.1,
                    "max_asset_class_exposure_pct": 0.6,
                }
            }
        },
    )
    monkeypatch.setattr(
        admin_routes.firm_orchestrator,
        "list_blocked_trades",
        lambda limit=12: [
            {"ts": "2026-05-24T00:00:00Z", "symbol": "AAPL", "reason": "sector_limit_breach", "status": "blocked"}
        ],
    )
    monkeypatch.setattr(admin_routes, "_record_runtime_control_event", lambda **kwargs: {})  # noqa: ARG005

    client = _client()

    sector_response = client.get("/api/admin/policy/sector_limits")
    position_response = client.get("/api/admin/policy/position_limits")
    threshold_response = client.get("/api/admin/policy/approval-thresholds")
    breach_response = client.get("/api/admin/risk/breach-history")

    assert sector_response.status_code == 200
    assert sector_response.json()["rows"][0]["sector"] in {"Tech", "Rates", "Finance"}

    assert position_response.status_code == 200
    assert position_response.json()["max_single_position_pct"] == 8.0

    assert threshold_response.status_code == 200
    assert threshold_response.json()["max_order_notional_usd"] == 100000.0

    update_response = client.put(
        "/api/admin/policy/approval-thresholds",
        json={
            "max_order_notional_usd": 150000,
            "min_cash_reserve_pct": 0.12,
            "max_asset_class_exposure_pct": 0.55,
            "reason": "manual threshold reset",
        },
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["max_order_notional_usd"] == 150000.0
    assert body["min_cash_reserve_pct"] == 0.12
    assert body["max_asset_class_exposure_pct"] == 0.55

    assert breach_response.status_code == 200
    assert breach_response.json()["items"][0]["reason"] == "sector_limit_breach"

