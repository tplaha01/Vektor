from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.broker.paper import PaperBroker
from app.fund.audit_log import AuditLog
from app.fund.agent_runtime import FundAgentRuntime
from app.fund.decision_ledger import DecisionLedger
from app.fund.knowledge_graph import KnowledgeGraph
from app.fund.openclaw_command_adapter import OpenClawCommandAdapter
from app.fund.openclaw_ingest import OpenClawIngestService
from app.fund.orchestrator import FirmOrchestrator
from app.fund.policy_gate import PolicyGate
from app.fund.research_memory import ResearchMemoryStore
from app.fund.router import get_agent_runtime, get_openclaw_command_adapter, get_orchestrator, router
from app.fund.sentiment_ingest import SentimentIngestService
from app.fund.task_bus import TaskBus


def _build_client() -> TestClient:
    audit = AuditLog()
    bus = TaskBus()
    orchestrator = FirmOrchestrator(
        task_bus_service=bus,
        decision_ledger_service=DecisionLedger(),
        audit_log_service=audit,
        policy_gate_service=PolicyGate(),
        openclaw_service=OpenClawIngestService(token="test-openclaw-token", log=audit),
        research_memory_store=ResearchMemoryStore(),
        sentiment_store=SentimentIngestService(),
        broker=PaperBroker(),
        price_lookup=lambda _symbol: 100.0,
        knowledge_graph_service=KnowledgeGraph(enabled=True, persist=False, graphify_sync_enabled=False),
    )
    runtime = FundAgentRuntime(
        orchestrator=orchestrator,
        task_bus_service=bus,
        enabled=True,
        poll_interval_seconds=0.05,
    )
    command_adapter = OpenClawCommandAdapter(
        runtime=runtime,
        token="test-openclaw-token",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        log=audit,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    app.dependency_overrides[get_openclaw_command_adapter] = lambda: command_adapter
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

    budget_config = client.post(
        "/fund/allocator/allocate",
        json={
            "run_id": "run-budget-1",
            "total_capital_usd": 1000,
            "reserve_cash_usd": 0,
            "target_weights": {"long_term": 0.7, "recurring": 0.2, "tactical": 0.1},
        },
    )
    assert budget_config.status_code == 200

    budget_research = client.post(
        "/fund/research/reports",
        json={
            "run_id": "run-budget-1",
            "agent_id": "researcher-budget",
            "asset_universe": ["MSFT"],
            "summary": "Budget test report for MSFT.",
            "confidence": 0.6,
            "provenance": [{"source_type": "data", "source_id": "dataset-budget-1"}],
        },
    )
    assert budget_research.status_code == 200
    budget_report_id = budget_research.json()["report_id"]

    budget_thesis = client.post(
        "/fund/theses",
        json={
            "run_id": "run-budget-1",
            "agent_id": "fund-manager-budget",
            "sleeve": "tactical",
            "report_ids": [budget_report_id],
            "statement": "Budget constrained tactical buy.",
            "conviction": 0.7,
        },
    )
    assert budget_thesis.status_code == 200
    budget_thesis_id = budget_thesis.json()["thesis_id"]

    budget_blocked = client.post(
        "/fund/decisions/execute",
        json={
            "run_id": "run-budget-1",
            "agent_id": "trader-budget",
            "thesis_id": budget_thesis_id,
            "symbol": "MSFT",
            "side": "buy",
            "quantity": 2,
            "price": 100,
        },
    )
    assert budget_blocked.status_code == 200
    budget_blocked_payload = budget_blocked.json()
    assert budget_blocked_payload["status"] == "blocked"
    assert "sleeve_budget_exceeded" in budget_blocked_payload["reasons"]

    budgets = client.get("/fund/sleeves/budgets?run_id=run-budget-1")
    assert budgets.status_code == 200
    assert budgets.json()["runs"][0]["run_id"] == "run-budget-1"

    pending = client.get("/fund/decisions/pending")
    assert pending.status_code == 200
    assert isinstance(pending.json(), list)

    tasks = client.get("/fund/agents/tasks/active")
    assert tasks.status_code == 200
    assert isinstance(tasks.json(), list)

    task_history = client.get("/fund/agents/tasks/history?limit=200&run_id=run-hedge-1")
    assert task_history.status_code == 200
    assert any(row.get("run_id") == "run-hedge-1" for row in task_history.json())

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

    openclaw_command = client.post(
        "/fund/openclaw/commands",
        headers={"X-OpenClaw-Token": "test-openclaw-token"},
        json={
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "run_id": "run-hedge-1",
            "text": "research and trade aapl",
        },
    )
    assert openclaw_command.status_code == 200
    assert openclaw_command.json()["accepted"] is True

    command_health = client.get("/fund/openclaw/commands/health")
    assert command_health.status_code == 200
    assert command_health.json()["accepted_count"] >= 1

    knowledge_events = client.get("/fund/knowledge/events?limit=200")
    assert knowledge_events.status_code == 200
    assert len(knowledge_events.json()) > 0

    lineage = client.get(f"/fund/knowledge/lineage?decision_id={execution_payload['decision_id']}&limit=200")
    assert lineage.status_code == 200
    assert len(lineage.json()) > 0

    stats = client.get("/fund/knowledge/stats")
    assert stats.status_code == 200
    assert stats.json()["event_count"] >= len(lineage.json())

    stream_status = client.get("/fund/stream/status")
    assert stream_status.status_code == 200
    assert stream_status.json()["event_count"] >= 1
