from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


class _StubRuntime:
    def __init__(self, *, started: bool = True):
        self._started = started
        self.calls = []

    def is_started(self) -> bool:
        return self._started

    def enqueue_signal_swarm(self, **kwargs):  # noqa: ANN003
        self.calls.append(dict(kwargs))
        return {
            "command_id": "swarm-test-1",
            "signal_pack_id": "sigpack-test-1",
            "role": "signal_swarm",
            "run_id": kwargs.get("run_id"),
            "status": "queued",
            "task_ids": ["task-1", "task-2"],
        }


class _StubOrchestrator:
    def __init__(self, history_rows: list[dict], timeline_rows: list[dict] | None = None):
        self._history_rows = history_rows
        self._timeline_rows = timeline_rows or []

    def list_task_history(self, **kwargs):  # noqa: ANN003
        return list(self._history_rows)

    def audit_timeline_for_order(self, order_id: str):  # noqa: ARG002
        return list(self._timeline_rows)


class _StubGuard:
    def __init__(self, *, halted: bool, reason: str | None = None):
        self._halted = halted
        self._reason = reason

    def halted(self) -> bool:
        return self._halted

    def halt_reason(self) -> str | None:
        return self._reason

    def status(self) -> dict:
        return {
            "strict_real_data_only": True,
            "halted": self._halted,
            "halt_reason": self._reason,
            "halted_at": "2026-04-17T00:00:00Z" if self._halted else None,
            "data_source_status": "Fallback" if self._halted else "Provider",
            "providers": [],
            "last_event": None,
        }


class _StubLedger:
    def list_events(self, limit=-1):  # noqa: ARG002
        return [
            {
                "event_id": "dle-1",
                "event_type": "decision.status_updated",
                "decision_id": "decision-1",
                "ts": "2026-04-17T00:00:03Z",
                "payload": {"status": "executed"},
            }
        ]


def _client():
    app = FastAPI()
    app.include_router(admin_routes.router)
    return TestClient(app)


def test_functional_verify_endpoint_reports_passed(monkeypatch):
    run_id = "run-functional-verify-test-1"
    history = [
        {
            "task_id": "task-1",
            "run_id": run_id,
            "agent_id": "api.admin",
            "role": "technical_analyst",
            "status": "completed",
            "event": "status_update",
            "ts": "2026-04-17T00:00:01Z",
            "details": {"symbol": "AAPL", "report_id": "report-1"},
        },
        {
            "task_id": "task-2",
            "run_id": run_id,
            "agent_id": "fund_manager_agent",
            "role": "fund_manager",
            "status": "completed",
            "event": "status_update",
            "ts": "2026-04-17T00:00:02Z",
            "details": {"decision_id": "decision-1"},
        },
        {
            "task_id": "task-3",
            "run_id": run_id,
            "agent_id": "trader_agent",
            "role": "trader",
            "status": "completed",
            "event": "status_update",
            "ts": "2026-04-17T00:00:03Z",
            "details": {"decision_id": "decision-1", "order_id": "order-1"},
        },
        {
            "task_id": "task-4",
            "run_id": run_id,
            "agent_id": "blog_writer_agent",
            "role": "blog_writer",
            "status": "completed",
            "event": "status_update",
            "ts": "2026-04-17T00:00:04Z",
            "details": {"post_ids": ["blog-1"]},
        },
    ]
    timeline = [
        {
            "source": "decision_ledger",
            "event_id": "dle-1",
            "event_type": "execution.submitted",
            "timestamp": "2026-04-17T00:00:03Z",
            "payload": {"order_id": "order-1"},
        }
    ]

    monkeypatch.setattr(admin_routes, "fund_agent_runtime", _StubRuntime(started=True))
    monkeypatch.setattr(admin_routes, "firm_orchestrator", _StubOrchestrator(history, timeline))
    monkeypatch.setattr(admin_routes, "decision_ledger", _StubLedger())
    monkeypatch.setattr(admin_routes, "data_integrity_guard", _StubGuard(halted=False))

    client = _client()
    response = client.post(
        "/api/admin/system/functional/verify",
        json={"run_id": run_id, "symbol": "AAPL", "timeout_seconds": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "passed"
    assert body["run_id"] == run_id
    assert body["pipeline"]["symbol"] == "AAPL"
    assert body["pipeline"]["decision_id"] == "decision-1"
    assert body["pipeline"]["order_id"] == "order-1"
    assert "blog-1" in body["pipeline"]["blog_post_ids"]
    assert body["lineage_detail_path"] == f"/api/admin/lineage/run/{run_id}"


def test_functional_verify_endpoint_rejects_when_halted(monkeypatch):
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", _StubRuntime(started=True))
    monkeypatch.setattr(admin_routes, "firm_orchestrator", _StubOrchestrator([]))
    monkeypatch.setattr(admin_routes, "decision_ledger", _StubLedger())
    monkeypatch.setattr(
        admin_routes,
        "data_integrity_guard",
        _StubGuard(halted=True, reason="real_data_required:provider:fallback"),
    )

    client = _client()
    response = client.post("/api/admin/system/functional/verify", json={"symbol": "SPY"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "system_halted"


def test_functional_verify_endpoint_reports_failed_on_analyst_failure(monkeypatch):
    run_id = "run-functional-verify-fail-1"
    history = [
        {
            "task_id": "task-1",
            "run_id": run_id,
            "agent_id": "api.admin",
            "role": "fundamental_analyst",
            "status": "failed",
            "event": "status_update",
            "ts": "2026-04-17T00:00:01Z",
            "details": {"symbol": "SPY", "error": "ai_role_adapter_invalid_json_response"},
        }
    ]

    monkeypatch.setattr(admin_routes, "fund_agent_runtime", _StubRuntime(started=True))
    monkeypatch.setattr(admin_routes, "firm_orchestrator", _StubOrchestrator(history))
    monkeypatch.setattr(admin_routes, "decision_ledger", _StubLedger())
    monkeypatch.setattr(admin_routes, "data_integrity_guard", _StubGuard(halted=False))

    client = _client()
    response = client.post(
        "/api/admin/system/functional/verify",
        json={"run_id": run_id, "symbol": "SPY", "timeout_seconds": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "failed"
    assert body["pipeline"]["terminal_failure"] is True
    assert body["pipeline"]["analyst_failed_roles"]["fundamental_analyst"] == "ai_role_adapter_invalid_json_response"
