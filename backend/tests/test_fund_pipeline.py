from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.broker.paper import PaperBroker
from app.fund.audit_log import AuditLog
from app.fund.decision_ledger import DecisionLedger
from app.fund.openclaw_ingest import OpenClawIngestService
from app.fund.orchestrator import FirmOrchestrator
from app.fund.policy_gate import PolicyGate
from app.fund.research_memory import ResearchMemoryStore
from app.fund.router import get_orchestrator, router
from app.fund.sentiment_ingest import SentimentIngestService
from app.fund.task_bus import TaskBus


def _build_client() -> TestClient:
    audit = AuditLog()
    orchestrator = FirmOrchestrator(
        task_bus_service=TaskBus(),
        decision_ledger_service=DecisionLedger(),
        audit_log_service=audit,
        policy_gate_service=PolicyGate(),
        openclaw_service=OpenClawIngestService(token="test-openclaw-token", log=audit),
        research_memory_store=ResearchMemoryStore(),
        sentiment_store=SentimentIngestService(),
        broker=PaperBroker(),
        price_lookup=lambda _symbol: 100.0,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    return TestClient(app)


def test_research_to_execution_pipeline_and_inspection_endpoints():
    client = _build_client()

    research = client.post(
        "/fund/research/reports",
        json={
            "run_id": "run-hedge-1",
            "agent_id": "researcher-1",
            "asset_universe": ["AAPL", "MSFT"],
            "summary": "AAPL has positive revisions and momentum.",
            "confidence": 0.8,
            "provenance": [{"source_type": "data", "source_id": "dataset-1"}],
        },
    )
    assert research.status_code == 200
    report_id = research.json()["report_id"]

    thesis = client.post(
        "/fund/theses",
        json={
            "run_id": "run-hedge-1",
            "agent_id": "fund-manager-1",
            "sleeve": "tactical",
            "report_ids": [report_id],
            "statement": "Buy AAPL into earnings drift.",
            "conviction": 0.74,
        },
    )
    assert thesis.status_code == 200
    thesis_id = thesis.json()["thesis_id"]

    executed = client.post(
        "/fund/decisions/execute",
        json={
            "run_id": "run-hedge-1",
            "agent_id": "trader-1",
            "thesis_id": thesis_id,
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10,
            "price": 100,
        },
    )
    assert executed.status_code == 200
    execution_payload = executed.json()
    assert execution_payload["status"] == "executed"
    order_id = execution_payload["order_id"]
    assert order_id is not None

    timeline = client.get(f"/fund/audit/orders/{order_id}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.json()) > 0

    blocked = client.post(
        "/fund/decisions/execute",
        json={
            "run_id": "run-hedge-1",
            "agent_id": "trader-1",
            "thesis_id": thesis_id,
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 500,
            "price": 100,
        },
    )
    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert blocked_payload["status"] == "blocked"
    assert "order_notional_limit_exceeded" in blocked_payload["reasons"]

    blocked_list = client.get("/fund/trades/blocked?limit=10")
    assert blocked_list.status_code == 200
    assert len(blocked_list.json()) >= 1

    pending = client.get("/fund/decisions/pending")
    assert pending.status_code == 200
    assert isinstance(pending.json(), list)

    tasks = client.get("/fund/agents/tasks/active")
    assert tasks.status_code == 200
    assert isinstance(tasks.json(), list)

    unauthorized_openclaw = client.post(
        "/fund/openclaw/ingest",
        headers={"X-OpenClaw-Token": "wrong-token"},
        json={"kind": "research_report", "payload": {"run_id": "run-hedge-1"}},
    )
    assert unauthorized_openclaw.status_code == 401

    authorized_openclaw = client.post(
        "/fund/openclaw/ingest",
        headers={"X-OpenClaw-Token": "test-openclaw-token"},
        json={"kind": "research_report", "payload": {"run_id": "run-hedge-1", "agent_id": "openclaw-1"}},
    )
    assert authorized_openclaw.status_code == 200
    assert authorized_openclaw.json()["accepted"] is True
