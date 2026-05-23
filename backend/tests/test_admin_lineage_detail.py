from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes
from app.broker.paper import PaperBroker
from app.fund.audit_log import AuditLog
from app.fund.contracts import DecisionRecord, Sleeve
from app.fund.decision_ledger import DecisionLedger
from app.fund.knowledge_graph import KnowledgeGraph
from app.fund.orchestrator import FirmOrchestrator
from app.fund.policy_gate import PolicyGate
from app.fund.research_memory import ResearchMemoryStore
from app.fund.sentiment_ingest import SentimentIngestService
from app.fund.task_bus import TaskBus
from app.storage import db as storage_db


def _build_orchestrator():
    bus = TaskBus()
    audit = AuditLog()
    ledger = DecisionLedger()
    orchestrator = FirmOrchestrator(
        task_bus_service=bus,
        decision_ledger_service=ledger,
        audit_log_service=audit,
        policy_gate_service=PolicyGate(),
        research_memory_store=ResearchMemoryStore(),
        sentiment_store=SentimentIngestService(),
        broker=PaperBroker(),
        price_lookup=lambda _symbol: 100.0,
        knowledge_graph_service=KnowledgeGraph(enabled=True, persist=False, graphify_sync_enabled=False),
    )
    return bus, orchestrator, ledger


def test_lineage_run_detail_endpoint_returns_drilldown(monkeypatch):
    bus, orchestrator, ledger = _build_orchestrator()
    run_id = "run-lineage-detail-1"

    analyst_task = bus.create_task(
        run_id=run_id,
        agent_id="ceo",
        role="technical_analyst",
        payload={"symbol": "AAPL", "signal_pack_id": "sigpack-1", "report_ids": ["report-1"]},
        priority=9,
    )
    bus.set_status(
        analyst_task.task_id,
        "completed",
        {"report_id": "report-1", "signal_pack_id": "sigpack-1", "symbol": "AAPL"},
    )
    trader_task = bus.create_task(
        run_id=run_id,
        agent_id="trader_agent",
        role="trader",
        payload={"symbol": "AAPL", "decision_id": "decision-1"},
        priority=8,
    )
    bus.set_status(
        trader_task.task_id,
        "blocked",
        {"decision_id": "decision-1", "reason": "broker_error:insufficient_cash"},
    )
    blog_task = bus.create_task(
        run_id=run_id,
        agent_id="blog_writer_agent",
        role="blog_writer",
        payload={"report_ids": ["report-1"]},
        priority=6,
    )
    bus.set_status(blog_task.task_id, "completed", {"post_ids": ["blog-1"]})

    ledger.add_decision(
        DecisionRecord(
            decision_id="decision-1",
            run_id=run_id,
            agent_id="trader_agent",
            sleeve=Sleeve.TACTICAL,
            thesis_id="thesis-1",
            risk_id="risk-1",
            intent_id="intent-1",
            status="blocked",
        )
    )
    ledger.update_status("decision-1", "blocked", {"reason": "broker_error:insufficient_cash"})

    monkeypatch.setattr(admin_routes, "firm_orchestrator", orchestrator)
    monkeypatch.setattr(admin_routes, "decision_ledger", ledger)
    monkeypatch.setattr(
        storage_db,
        "load_blog_post",
        lambda post_id_or_slug: {
            "id": "blog-1",
            "slug": "market-update",
            "title": "Market Update",
            "published_at": "2026-04-17T00:00:00Z",
        }
        if str(post_id_or_slug) == "blog-1"
        else None,
    )

    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app)

    response = client.get(f"/api/admin/lineage/run/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["summary"]["symbol"] == "AAPL"
    assert body["summary"]["decision_id"] == "decision-1"
    assert body["summary"]["lineage_detail_path"] == f"/api/admin/lineage/run/{run_id}"
    assert body["summary"]["decision_detail_path"] == "/api/admin/decisions/decision-1"
    assert "report-1" in body["related_research_report_ids"]
    assert "blog-1" in body["related_blog_post_ids"]
    assert body["decision"]["decision_id"] == "decision-1"
    assert len(body["task_events"]) >= 3

    recent = client.get("/api/admin/lineage/recent?limit=5")
    assert recent.status_code == 200
    rows = recent.json()["rows"]
    target = next((row for row in rows if row.get("run_id") == run_id), None)
    assert target is not None
    assert target["lineage_detail_path"] == f"/api/admin/lineage/run/{run_id}"
    assert target["decision_detail_path"] == "/api/admin/decisions/decision-1"
    assert "report-1" in target["report_ids"]

    decision_detail = client.get("/api/admin/decisions/decision-1")
    assert decision_detail.status_code == 200
    detail_body = decision_detail.json()
    assert detail_body["decision_id"] == "decision-1"
    assert detail_body["lineage_detail_path"] == f"/api/admin/lineage/run/{run_id}"


def test_decision_detail_prefers_execution_metadata_scoring(monkeypatch):
    _, orchestrator, ledger = _build_orchestrator()
    run_id = "run-decision-score-1"
    decision_id = "decision-score-1"

    ledger.add_decision(
        DecisionRecord(
            decision_id=decision_id,
            run_id=run_id,
            agent_id="trader-agent",
            sleeve=Sleeve.TACTICAL,
            thesis_id="thesis-score-1",
            risk_id="risk-score-1",
            intent_id="intent-score-1",
            status="executed",
        )
    )
    ledger.add_event(
        event_type="execution.processed",
        decision_id=decision_id,
        order_id="ord-1",
        payload={
            "status": "executed",
            "order": {
                "id": "ord-1",
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 5,
                "avg_price": 100.0,
            },
            "intent_metadata": {
                "decision_scoring": {
                    "score": 0.91,
                    "confidence": 0.88,
                    "direction": "long_bias",
                    "asset_class": "equities",
                    "strategy_family": "deterministic_ml_firm_engine",
                    "horizon": "swing",
                    "math_summary": "from_intent_metadata",
                    "metrics": {"ml_confidence": 0.88},
                },
                "deterministic_ml_signal": {
                    "score": 0.91,
                    "confidence": 0.88,
                    "model": {"selected": "deterministic_ml"},
                },
            },
        },
    )

    monkeypatch.setattr(admin_routes, "firm_orchestrator", orchestrator)
    monkeypatch.setattr(admin_routes, "decision_ledger", ledger)
    monkeypatch.setattr(
        orchestrator,
        "latest_discovery_opportunity",
        lambda **_: {
            "score": -0.35,
            "confidence": 0.1,
            "direction": "short_bias",
            "asset_class": "equities",
            "strategy_family": "fallback_discovery",
            "horizon": "intraday",
            "ml": {"math_summary": "from_discovery"},
        },
    )

    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app)

    response = client.get(f"/api/admin/decisions/{decision_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["decision_id"] == decision_id
    assert body["order_id"] == "ord-1"
    assert body["decision_scoring"]["score"] == 0.91
    assert body["decision_scoring"]["math_summary"] == "from_intent_metadata"
    assert body["trade_rationale"]["execution_status"] == "executed"
    assert body["deterministic_ml_signal"]["score"] == 0.91
