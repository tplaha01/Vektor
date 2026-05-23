from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes
from app.fund.contracts import DecisionRecord, Sleeve
from app.fund.decision_ledger import DecisionLedger


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


class _StubBroker:
    def __init__(self):
        self.cash = 250.0
        self.positions = {"AAPL": {"symbol": "AAPL", "qty": 1.0, "avg_price": 100.0}}
        self.order_history = [{"id": "1"}]
        self.persist_calls = 0

    def persist_state(self):
        self.persist_calls += 1


class _Settings:
    BROKER = "paper"


class _StubGuard:
    def __init__(self, *, halted: bool, reason: str | None = None):
        self._halted = halted
        self._reason = reason
        self.clear_calls = 0
        self.set_strict_calls = 0
        self.recorded_events: list[dict] = []
        self._strict_real_data_only = True

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

    def set_strict_mode(self, enabled: bool, *, reason: str):  # noqa: ARG002
        self.set_strict_calls += 1
        previous = self._strict_real_data_only
        self._strict_real_data_only = bool(enabled)
        auto_cleared = False
        if not enabled and self._halted:
            self._halted = False
            self._reason = None
            auto_cleared = True
        return {
            "updated_at": "2026-04-17T00:00:00Z",
            "reason": reason,
            "strict_real_data_only_previous": previous,
            "strict_real_data_only": bool(enabled),
            "halt_auto_cleared": auto_cleared,
            "status": self.status(),
        }

    def record_provider_event(self, *, provider: str, mode: str, symbol=None, detail=None):
        self.recorded_events.append(
            {
                "provider": provider,
                "mode": mode,
                "symbol": symbol,
                "detail": detail,
            }
        )
        if self._strict_real_data_only and mode in {"fallback", "failed"}:
            self._halted = True
            self._reason = f"real_data_required:{provider}:{detail or mode}"

    def status(self):
        return {
            "halted": self._halted,
            "halt_reason": self._reason,
            "halted_at": "2026-04-17T00:00:00Z" if self._halted else None,
            "strict_real_data_only": self._strict_real_data_only,
            "data_source_status": "Fallback" if self._halted else "Provider",
            "providers": [],
            "last_event": self.recorded_events[-1] if self.recorded_events else None,
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


def test_set_strict_mode_endpoint_updates_guard(monkeypatch):
    runtime = _StubRuntime(started=True)
    guard = _StubGuard(halted=False, reason=None)
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "data_integrity_guard", guard)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)

    client = _client()
    response = client.post(
        "/api/admin/system/data-integrity/strict-mode",
        json={"enabled": False, "reason": "maintenance_window"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["action"] == "strict_mode_updated"
    assert body["strict_real_data_only"] is False
    assert guard.set_strict_calls == 1
    assert len(graph.events) == 1
    assert graph.events[0]["event_type"] == "runtime.control.set_strict_mode"


def test_deterministic_ml_recover_disables_strict_mode_and_clears_halt(monkeypatch):
    runtime = _StubRuntime(started=False)
    guard = _StubGuard(halted=True, reason="real_data_required:provider:fallback")
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "data_integrity_guard", guard)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)

    client = _client()
    response = client.post(
        "/api/admin/system/deterministic-ml/recover",
        json={"reason": "deterministic_ml_test"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["action"] == "deterministic_ml_recovered"
    assert body["halted"] is False
    assert body["strict_real_data_only"] is False
    assert body["halt_auto_cleared"] is True
    assert guard.set_strict_calls == 1
    assert graph.events[0]["event_type"] == "runtime.control.deterministic_ml_recover"
    assert graph.events[0]["payload"]["status"] == "recovered"


def test_data_integrity_drill_endpoint_trips_halt_on_fallback(monkeypatch):
    runtime = _StubRuntime(started=True)
    guard = _StubGuard(halted=False, reason=None)
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "data_integrity_guard", guard)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)

    client = _client()
    response = client.post(
        "/api/admin/system/data-integrity/drill",
        json={
            "provider": "finnhub_news",
            "mode": "fallback",
            "symbol": "SPY",
            "detail": "provider_timeout",
            "reason": "chaos_test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["action"] == "data_integrity_drill_recorded"
    assert body["halted"] is True
    assert "real_data_required:finnhub_news:provider_timeout" in str(body["halt_reason"])
    assert len(guard.recorded_events) == 1
    assert guard.recorded_events[0]["symbol"] == "SPY"
    assert len(graph.events) == 1
    assert graph.events[0]["event_type"] == "runtime.control.data_integrity_drill"


def test_paper_broker_capital_top_up_endpoint_updates_cash(monkeypatch):
    runtime = _StubRuntime(started=True)
    guard = _StubGuard(halted=False, reason=None)
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    broker = _StubBroker()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "data_integrity_guard", guard)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)
    monkeypatch.setattr(admin_routes, "broker", broker)
    monkeypatch.setattr(admin_routes, "get_settings", lambda: _Settings())

    client = _client()
    response = client.post(
        "/api/admin/system/paper-broker/capital",
        json={"action": "top_up", "amount_usd": 1000, "reason": "functional_verify_funding"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["after"]["cash_usd"] == 1250.0
    assert broker.persist_calls == 1
    assert len(graph.events) == 1
    assert graph.events[0]["event_type"] == "runtime.control.paper_broker_capital"


def test_ops_panel_endpoint_returns_status_and_lineage(monkeypatch):
    runtime = _StubRuntime(started=True)
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)
    monkeypatch.setattr(admin_routes, "get_settings", lambda: _Settings())

    client = _client()
    response = client.get("/api/admin/system/ops/panel?limit=3")
    assert response.status_code == 200
    body = response.json()
    assert "status_badges" in body
    assert "runtime_control" in body
    assert "recent_lineage" in body
    assert "recent_trades" in body
    assert isinstance(body["recent_trades"], list)


def test_ops_panel_endpoint_includes_trade_rationale(monkeypatch):
    runtime = _StubRuntime(started=True)
    guard = _StubGuard(halted=False, reason=None)
    graph = _StubKnowledgeGraph()
    audit = _StubAudit()
    ledger = DecisionLedger()
    decision_id = "decision-ops-panel-1"
    ledger.add_decision(
        DecisionRecord(
            decision_id=decision_id,
            run_id="run-ops-panel-1",
            agent_id="trader",
            sleeve=Sleeve.TACTICAL,
            thesis_id="thesis-ops-panel-1",
            risk_id="risk-ops-panel-1",
            intent_id="intent-ops-panel-1",
            status="executed",
        )
    )
    ledger.add_event(
        event_type="execution.processed",
        decision_id=decision_id,
        order_id="ord-ops-panel-1",
        payload={
            "status": "executed",
            "order": {"id": "ord-ops-panel-1", "symbol": "NVDA", "side": "buy", "quantity": 2, "avg_price": 100.0},
            "intent_metadata": {
                "decision_scoring": {
                    "score": 0.77,
                    "confidence": 0.74,
                    "direction": "long_bias",
                    "asset_class": "equities",
                    "strategy_family": "deterministic_ml_firm_engine",
                    "horizon": "swing",
                    "math_summary": "ops_panel_metadata",
                    "metrics": {"ml_confidence": 0.74},
                }
            },
        },
    )

    monkeypatch.setattr(admin_routes, "fund_agent_runtime", runtime)
    monkeypatch.setattr(admin_routes, "data_integrity_guard", guard)
    monkeypatch.setattr(admin_routes, "knowledge_graph", graph)
    monkeypatch.setattr(admin_routes, "audit_log", audit)
    monkeypatch.setattr(admin_routes, "decision_ledger", ledger)
    monkeypatch.setattr(admin_routes, "get_settings", lambda: _Settings())

    client = _client()
    response = client.get("/api/admin/system/ops/panel?limit=5")
    assert response.status_code == 200
    body = response.json()
    rows = body.get("recent_trades") if isinstance(body.get("recent_trades"), list) else []
    target = next((row for row in rows if row.get("decision_id") == decision_id), None)
    assert target is not None
    assert target["order_id"] == "ord-ops-panel-1"
    assert target["decision_scoring"]["score"] == 0.77
    assert target["math_summary"] == "ops_panel_metadata"
