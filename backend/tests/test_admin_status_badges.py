from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


class _StubRuntime:
    def __init__(self, payload: dict):
        self._payload = payload

    def status(self) -> dict:
        return dict(self._payload)


class _Settings:
    BROKER = "paper"


def _base_worker(role: str, *, running: bool = True, last_error: str | None = None) -> dict:
    return {
        "role": role,
        "started": True,
        "running": running,
        "last_error": last_error,
        "last_heartbeat_at": "2026-04-17T00:00:00Z",
        "completed_count": 1,
        "failed_count": 0,
        "blocked_count": 0,
    }


def _build_runtime_payload(*, halted: bool, halt_reason: str | None = None) -> dict:
    roles = [
        "technical_analyst",
        "fundamental_analyst",
        "sentiment_analyst",
        "ml_timeseries_analyst",
        "insight_researcher",
        "hedge_fund_researcher",
        "fund_manager",
        "trader",
        "risk_auditor",
        "blog_writer",
    ]
    workers = [_base_worker(role) for role in roles]
    return {
        "started": True,
        "workers": workers,
        "ai_role_adapter": {
            "enabled": True,
            "provider": "router",
            "mode": "multi_vendor_router",
            "default_model": "gemini-2.5-flash-lite",
            "role_models": {},
            "last_error": None,
            "default_route": ["gemini_flash_lite", "groq"],
            "role_routes": {
                "technical_analyst": ["gemini_flash_lite", "groq"],
            },
            "providers": {
                "gemini_flash_lite": {
                    "quota_state": "available",
                    "default_model": "gemini-2.5-flash-lite",
                },
                "groq": {
                    "quota_state": "available",
                    "default_model": "gpt-oss-20b",
                },
            },
            "role_runtime": {
                "technical_analyst": {
                    "route": ["gemini_flash_lite", "groq"],
                    "last_provider": "gemini_flash_lite",
                    "last_model": "gemini-2.5-flash-lite",
                    "fallback_used": False,
                    "failover_count": 0,
                }
            },
            "gateway": {
                "enabled": False,
                "base_url": None,
            },
        },
        "data_integrity": {
            "strict_real_data_only": True,
            "halted": halted,
            "halt_reason": halt_reason,
            "halted_at": "2026-04-17T00:00:00Z" if halted else None,
            "data_source_status": "Fallback" if halted else "Provider",
            "providers": [],
            "last_event": None,
        },
    }


def test_status_badges_endpoint_reports_healthy(monkeypatch):
    runtime = _StubRuntime(_build_runtime_payload(halted=False))
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "get_settings", lambda: _Settings())

    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app)

    response = client.get("/api/admin/system/status-badges")
    assert response.status_code == 200
    body = response.json()
    assert body["orchestration"]["status"] == "Healthy"
    assert body["data_source"]["status"] == "Provider"
    assert body["execution_mode"]["status"] == "Paper Only"
    assert body["llm_agent_health"]["status"] == "Healthy"
    assert len(body["llm_agent_health"]["by_role"]) == 6
    assert body["llm_agent_health"]["mode"] == "multi_vendor_router"
    assert body["llm_agent_health"]["default_route"] == ["gemini_flash_lite", "groq"]


def test_status_badges_endpoint_reports_degraded_when_halted(monkeypatch):
    runtime = _StubRuntime(
        _build_runtime_payload(
            halted=True,
            halt_reason="real_data_required:newsapi:missing_newsapi_key",
        )
    )
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "get_settings", lambda: _Settings())

    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app)

    response = client.get("/api/admin/system/status-badges")
    assert response.status_code == 200
    body = response.json()
    assert body["orchestration"]["status"] == "Degraded"
    assert body["data_source"]["status"] == "Fallback"
    assert body["llm_agent_health"]["status"] == "Degraded"
    assert body["halt"]["halted"] is True
    assert "real-data mode" in body["halt"]["message"]


def test_status_badges_endpoint_reports_degraded_on_provider_fallback(monkeypatch):
    payload = _build_runtime_payload(halted=False)
    payload["data_integrity"]["data_source_status"] = "Fallback"
    payload["data_integrity"]["providers"] = [
        {
            "provider": "finnhub_news",
            "mode": "fallback",
            "last_at": "2026-04-17T00:00:00Z",
            "symbol": "AAPL",
            "detail": "provider_timeout",
        }
    ]
    runtime = _StubRuntime(payload)
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "get_settings", lambda: _Settings())

    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app)

    response = client.get("/api/admin/system/status-badges")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"]["status"] == "Fallback"
    assert body["orchestration"]["status"] == "Degraded"
    assert body["orchestration"]["reason"] == "data_source_fallback_detected"
