from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


def _client():
    app = FastAPI()
    app.include_router(admin_routes.router)
    return TestClient(app)


def test_overview_fund_metric_endpoints(monkeypatch):
    summary = admin_routes.MetricsSummary(
        total_equity=125000.0,
        equity_change=25.0,
        account_equity=125000.0,
        external_capital_flow_usd=0.0,
        baseline_equity=100000.0,
        realized_pnl=12000.0,
        pnl_change=0.0,
        unrealized_pnl=3000.0,
        current_drawdown=1.5,
        drawdown_change=0.0,
        max_drawdown_ytd=4.2,
        max_drawdown_threshold=10.0,
        active_positions=3,
        win_rate=62.5,
        win_rate_change=0.0,
        sharpe_ratio=1.21,
        sharpe_change=0.0,
    )

    async def _metrics_summary():
        return summary

    monkeypatch.setattr(admin_routes, "get_metrics_summary", _metrics_summary)
    monkeypatch.setattr(
        admin_routes.performance_tracker,
        "summary",
        lambda: {
            "latest_snapshot": {
                "equity": 125000.0,
            },
            "inception_snapshot": {"equity": 100000.0},
            "track_record": {
                "sharpe_ratio": 1.21,
                "primary_benchmark_return_pct": 1.1,
                "max_drawdown_pct": 4.2,
            },
        },
    )
    monkeypatch.setattr(
        admin_routes.storage_db,
        "load_performance_snapshots",
        lambda limit=500: [
            {"recorded_at": "2026-05-01T00:00:00Z", "equity": 120000.0},
            {"recorded_at": "2026-05-20T00:00:00Z", "equity": 125000.0},
        ],
    )
    monkeypatch.setattr(
        admin_routes.risk,
        "status",
        lambda: {
            "drawdown_breaker": {
                "current_drawdown": 0.018,
                "max_drawdown_threshold": 0.10,
                "halted": False,
            }
        },
    )

    client = _client()

    nav = client.get("/api/admin/fund/nav")
    monthly = client.get("/api/admin/fund/monthly-pnl")
    sharpe = client.get("/api/admin/fund/sharpe")
    drawdown = client.get("/api/admin/fund/drawdown")

    assert nav.status_code == 200
    assert nav.json()["nav_current"] == 125000.0
    assert nav.json()["nav_change_pct"] == 25.0

    assert monthly.status_code == 200
    assert monthly.json()["monthly_pnl_usd"] == 5000.0
    assert monthly.json()["benchmark_pnl_pct"] == 1.1

    assert sharpe.status_code == 200
    assert sharpe.json()["rolling_30d"] == 1.21
    assert sharpe.json()["status"] == "healthy"

    assert drawdown.status_code == 200
    assert drawdown.json()["current_drawdown_pct"] == 1.8
    assert drawdown.json()["limit_pct"] == 10.0


def test_overview_runtime_portfolio_risk_and_alerts(monkeypatch):
    async def _status_badges():
        return {
            "orchestration": {"status": "Healthy"},
            "data_source": {"status": "Provider", "providers": []},
            "execution_mode": {"status": "Paper Only", "broker": "paper"},
            "llm_agent_health": {"status": "Healthy"},
        }

    async def _runtime_control():
        return {"runtime_started": True, "active_task_count": 2, "halted": False}

    async def _workers():
        return {
            "workers": [
                {"status": "running"},
                {"status": "running"},
                {"status": "running"},
                {"status": "running"},
            ]
        }

    monkeypatch.setattr(admin_routes, "get_system_status_badges", _status_badges)
    monkeypatch.setattr(admin_routes, "get_runtime_control_status", _runtime_control)
    monkeypatch.setattr(admin_routes, "get_agents_status", _workers)
    monkeypatch.setattr(
        admin_routes.broker,
        "list_positions",
        lambda _: [
            {"symbol": "AAPL", "market_value": 50000.0},
            {"symbol": "MSFT", "market_value": 25000.0},
        ],
    )
    monkeypatch.setattr(admin_routes.broker, "get_cash", lambda: 25000.0)
    monkeypatch.setattr(
        admin_routes.risk,
        "status",
        lambda: {
            "drawdown_breaker": {
                "current_drawdown": 0.012,
                "max_drawdown_threshold": 0.10,
                "halted": False,
            }
        },
    )
    monkeypatch.setattr(
        admin_routes.vektor_ceo_service,
        "risk_alerts",
        lambda: {"alerts": [{"severity": "medium", "type": "provider", "message": "Provider lag"}]},
    )
    monkeypatch.setattr(admin_routes.vektor_ceo_service, "pending_approvals", lambda: {"count": 2})

    client = _client()

    runtime = client.get("/api/admin/runtime/status")
    exposure = client.get("/api/admin/portfolio/exposure")
    risk = client.get("/api/admin/risk/status")
    alerts = client.get("/api/admin/alerts/pending")

    assert runtime.status_code == 200
    assert runtime.json()["runtime_status"] == "healthy"
    assert runtime.json()["agents_active"] == 4

    assert exposure.status_code == 200
    assert exposure.json()["equities_usd"] == 75000.0
    assert exposure.json()["cash_usd"] == 25000.0

    assert risk.status_code == 200
    assert risk.json()["status"] == "within_limits"
    assert risk.json()["max_drawdown_limit_pct"] == 10.0

    assert alerts.status_code == 200
    body = alerts.json()
    assert body["approval_count"] == 2
    assert body["pending_count"] >= 2
