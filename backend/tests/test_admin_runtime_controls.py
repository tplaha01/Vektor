from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


class _StubRuntime:
    def __init__(self, *, started: bool = True, autopilot_enabled: bool = True):
        self.started = started
        self.autopilot_enabled = autopilot_enabled
        self.start_calls = 0
        self.stop_calls = 0
        self.kick_calls = 0

    async def start(self):
        self.started = True
        self.start_calls += 1

    async def stop(self):
        self.started = False
        self.stop_calls += 1

    def is_started(self) -> bool:
        return self.started

    def kick_autopilot(self, run_id=None):
        self.kick_calls += 1
        if not self.started:
            return {"accepted": False, "reason": "runtime_not_started"}
        return {"accepted": True, "run_id": run_id or "run-test"}

    def status(self) -> dict:
        return {
            "started": self.started,
            "autopilot": {"enabled": self.autopilot_enabled, "running": False},
            "data_integrity": {
                "halted": False,
                "halt_reason": None,
                "halted_at": None,
                "strict_real_data_only": True,
            },
        }


class _StubKnowledgeGraph:
    def __init__(self):
        self.events = []

    def ingest(
        self,
        *,
        source: str,
        event_type: str,
        run_id=None,
        agent_id=None,
        payload=None,
        **_,
    ):
        event = {
            "event_id": f"kge-{len(self.events)+1:06d}",
            "source": source,
            "namespace": str(event_type).split(".", 1)[0] if "." in str(event_type) else "runtime",
            "event_type": event_type,
            "occurred_at": "2026-04-17T00:00:00Z",
            "run_id": run_id,
            "agent_id": agent_id,
            "payload": dict(payload or {}),
        }
        self.events.append(event)
        return event

    def list_events(self, *, limit=200, namespace=None, source=None, **_):
        rows = list(self.events)
        if namespace is not None:
            rows = [row for row in rows if row.get("namespace") == namespace]
        if source is not None:
            rows = [row for row in rows if row.get("source") == source]
        return list(reversed(rows))[:limit]


class _StubAudit:
    def __init__(self):
        self.rows = []

    def record(self, event_type: str, payload: dict):
        self.rows.append({"event_type": event_type, "payload": dict(payload)})
        return {"event_id": f"aevt-{len(self.rows):06d}", "event_type": event_type, "payload": dict(payload)}


class _StubGuard:
    def __init__(self, *, halted: bool, reason: str | None = None):
        self._halted = halted
        self._reason = reason
        self.clear_calls = 0

    def halted(self) -> bool:
        return self._halted

    def halt_reason(self) -> str | None:
        return self._reason

    def clear_halt(self, *, reason: str):
        self.clear_calls += 1
        self._halted = False
        self._reason = None
        return {
            "cleared": True,
            "cleared_at": "2026-04-17T00:00:00Z",
            "reason": reason,
            "previous_halt_reason": "real_data_required:test_provider:fallback",
            "previous_halted_at": "2026-04-17T00:00:00Z",
        }

    def status(self):
        return {
            "halted": self._halted,
            "halt_reason": self._reason,
            "halted_at": "2026-04-17T00:00:00Z" if self._halted else None,
            "strict_real_data_only": True,
        }


def _client():
    app = FastAPI()
    app.include_router(admin_routes.router)
    return TestClient(app)


def test_pause_runtime_endpoint_stops_runtime(monkeypatch):
    runtime = _StubRuntime(started=True)
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)

    client = _client()
    response = client.post("/api/admin/system/runtime/pause", json={"reason": "test_pause"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["action"] == "paused"
    assert body["runtime_started"] is False
    assert runtime.stop_calls == 1
    assert len(graph.events) == 1


def test_resume_runtime_endpoint_rejects_when_halted(monkeypatch):
    runtime = _StubRuntime(started=False)
    guard = _StubGuard(halted=True, reason="real_data_required:provider:fallback")
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "data_integrity_guard", guard)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)

    client = _client()
    response = client.post("/api/admin/system/runtime/resume", json={"reason": "test_resume"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "system_halted"
    assert len(graph.events) == 1
    assert graph.events[0]["event_type"] == "runtime.control.resume"
    assert graph.events[0]["payload"]["status"] == "rejected"


def test_clear_system_halt_endpoint_clears_guard(monkeypatch):
    runtime = _StubRuntime(started=False)
    guard = _StubGuard(halted=True, reason="real_data_required:provider:fallback")
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "data_integrity_guard", guard)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)

    client = _client()
    response = client.post("/api/admin/system/halt/clear", json={"reason": "manual_test_clear"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["action"] == "halt_cleared"
    assert body["cleared"] is True
    assert guard.clear_calls == 1
    assert len(graph.events) == 1


def test_kick_autopilot_endpoint_accepts(monkeypatch):
    runtime = _StubRuntime(started=True)
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)

    client = _client()
    response = client.post("/api/admin/system/autopilot/kick", json={"run_id": "run-test"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["accepted"] is True
    assert runtime.kick_calls == 1
    assert len(graph.events) == 1
    assert graph.events[0]["event_type"] == "runtime.control.kick_autopilot"


def test_runtime_control_history_endpoint_returns_rows(monkeypatch):
    graph = _StubKnowledgeGraph()
    graph.ingest(
        source="runtime",
        event_type="runtime.control.pause",
        run_id="run-admin-control-1",
        agent_id="api.admin",
        payload={"action": "pause", "status": "paused", "reason": "manual"},
    )
    graph.ingest(
        source="runtime",
        event_type="runtime.control.resume",
        run_id="run-admin-control-2",
        agent_id="api.admin",
        payload={"action": "resume", "status": "resumed", "reason": None},
    )
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)

    client = _client()
    response = client.get("/api/admin/system/control-history?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["rows"]) == 2
    assert body["rows"][0]["action"] == "resume"
    assert body["rows"][1]["action"] == "pause"
