import asyncio
from time import monotonic
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.broker.paper import PaperBroker
from app.fund.agent_runtime import FundAgentRuntime
from app.fund.ai_role_adapter import AIRoleAnalysis
from app.fund.audit_log import AuditLog
from app.fund.decision_ledger import DecisionLedger
from app.fund.knowledge_graph import KnowledgeGraph
from app.fund.openclaw_ingest import OpenClawIngestService
from app.fund.orchestrator import FirmOrchestrator
from app.fund.policy_gate import PolicyGate
from app.fund.research_memory import ResearchMemoryStore
from app.fund.router import get_agent_runtime, get_orchestrator, router
from app.fund.sentiment_ingest import SentimentIngestService
from app.fund.task_bus import TaskBus
from app.fund.contracts import ResearchReport as ContractResearchReport


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_stack():
    bus = TaskBus()
    audit = AuditLog()
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
    return bus, orchestrator, runtime


def _stub_discovery_opportunity(symbol: str, *, score: float, confidence: float) -> dict:
    return {
        "opportunity_id": f"opp-{symbol.lower()}",
        "run_id": "run-discovery-test",
        "agent_id": "world_scanner",
        "symbol": symbol,
        "asset_class": "equities",
        "strategy_family": "multi_signal_scout",
        "direction": "long_bias",
        "score": score,
        "confidence": confidence,
        "horizon": "swing",
        "thesis": f"{symbol} thesis",
        "catalysts": [f"{symbol} catalyst"],
        "evidence": [f"{symbol} evidence"],
        "ml": {
            "directional_probability_up": score,
            "technical_confidence": confidence,
            "ml_confidence": confidence,
            "sentiment_normalized": 0.5,
            "liquidity_score": 0.7,
            "volatility_score": 0.6,
            "news_intensity_count": 2,
            "regime_alignment": 0.7,
            "math_summary": f"{symbol} math",
        },
        "metadata": {"source": "test"},
        "status": "candidate",
    }


def test_ceo_command_endpoint_queues_role_task():
    _, orchestrator, runtime = _build_stack()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    client = TestClient(app)

    response = client.post(
        "/fund/ceo/commands",
        json={
            "run_id": "run-ceo-1",
            "agent_id": "ceo-1",
            "command": "research AAPL and prepare trade",
            "payload": {"symbol": "AAPL", "quantity": 1, "price": 100},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "insight_researcher"
    assert body["task_id"]


def test_knowledge_reset_endpoint_resets_and_seeds_event():
    _, orchestrator, runtime = _build_stack()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    client = TestClient(app)

    orchestrator.allocate_sleeves(run_id="run-kb-reset-1", total_capital_usd=100000, reserve_cash_usd=10000)
    before = client.get("/fund/knowledge/stats")
    assert before.status_code == 200
    assert before.json()["event_count"] >= 1

    response = client.post(
        "/fund/knowledge/reset",
        json={"run_id": "run-kb-reset-1", "agent_id": "ceo", "seed_event": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reset_result"]["reset"] is True
    assert body["stats"]["event_count"] == 1
    events = client.get("/fund/knowledge/events?limit=5").json()
    assert events[0]["event_type"] == "development.kb_reset"


def test_development_log_endpoint_graphifies_structured_entry():
    _, orchestrator, runtime = _build_stack()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    client = TestClient(app)

    response = client.post(
        "/fund/knowledge/development/log",
        json={
            "entry_id": "devlog-test-1",
            "stage": "start",
            "actor_name": "codex-worker-1",
            "actor_platform": "codex",
            "actor_model": "gpt-5.4",
            "actor_provider": "openai",
            "run_id": "run-devlog-1",
            "branch": "codex/devlog-test",
            "commit_start": "abc123",
            "scope": "Implement structured dev logs.",
            "files": ["Dev_Logs.md", "DevViktor.md"],
            "validation": "pending",
            "notes": "kickoff",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["event"]["event_type"] == "development.devlog.start"

    events = client.get("/fund/knowledge/events?namespace=development&limit=20").json()
    assert any(row["event_type"] == "development.devlog.start" for row in events)


def test_resolve_autopilot_symbols_marks_selected_and_pruned_capacity(monkeypatch):
    bus, orchestrator, _runtime = _build_stack()
    runtime = FundAgentRuntime(
        orchestrator=orchestrator,
        task_bus_service=bus,
        enabled=True,
        autopilot_dynamic_universe_enabled=True,
        autopilot_scout_symbols=("NVDA", "AAPL", "MSFT"),
        autopilot_scout_max_symbols=2,
        allow_cash_hold=True,
    )
    runtime._autopilot_last_run_id = "run-discovery-test"  # noqa: SLF001
    runtime._autopilot_scout_symbols = ("NVDA", "AAPL", "MSFT")  # noqa: SLF001

    opportunities = {
        "NVDA": _stub_discovery_opportunity("NVDA", score=0.88, confidence=0.82),
        "AAPL": _stub_discovery_opportunity("AAPL", score=0.79, confidence=0.76),
        "MSFT": _stub_discovery_opportunity("MSFT", score=0.74, confidence=0.72),
    }

    monkeypatch.setattr(runtime, "_score_autopilot_symbol", lambda symbol: dict(opportunities.get(symbol)))

    recorded: list[dict] = []
    original_record = orchestrator.record_discovery_opportunity

    def _capture(payload):  # noqa: ANN001
        result = original_record(payload)
        recorded.append(dict(result))
        return result

    monkeypatch.setattr(orchestrator, "record_discovery_opportunity", _capture)

    selected, scout_meta = runtime._resolve_autopilot_symbols()  # noqa: SLF001

    assert selected == ("NVDA", "AAPL")
    assert scout_meta["status_counts"]["selected"] == 2
    assert scout_meta["status_counts"]["pruned_capacity"] == 1

    latest_by_symbol = {row["symbol"]: row for row in recorded if row.get("symbol") != "CASH"}
    assert latest_by_symbol["NVDA"]["status"] == "selected"
    assert latest_by_symbol["AAPL"]["status"] == "selected"
    assert latest_by_symbol["MSFT"]["status"] == "pruned_capacity"
    assert latest_by_symbol["MSFT"]["metadata"]["discovery_reason"] == "wave_capacity_limit"


def test_resolve_autopilot_symbols_records_no_trade_when_thresholds_fail(monkeypatch):
    bus, orchestrator, _runtime = _build_stack()
    runtime = FundAgentRuntime(
        orchestrator=orchestrator,
        task_bus_service=bus,
        enabled=True,
        autopilot_dynamic_universe_enabled=True,
        autopilot_scout_symbols=("NVDA", "AAPL", "MSFT"),
        autopilot_scout_max_symbols=2,
        allow_cash_hold=True,
    )
    runtime._autopilot_last_run_id = "run-discovery-test"  # noqa: SLF001
    runtime._autopilot_scout_symbols = ("NVDA", "AAPL", "MSFT")  # noqa: SLF001

    opportunities = {
        "NVDA": _stub_discovery_opportunity("NVDA", score=0.41, confidence=0.45),
        "AAPL": _stub_discovery_opportunity("AAPL", score=0.38, confidence=0.40),
        "MSFT": _stub_discovery_opportunity("MSFT", score=0.36, confidence=0.35),
    }

    monkeypatch.setattr(runtime, "_score_autopilot_symbol", lambda symbol: dict(opportunities.get(symbol)))

    recorded: list[dict] = []
    original_record = orchestrator.record_discovery_opportunity

    def _capture(payload):  # noqa: ANN001
        result = original_record(payload)
        recorded.append(dict(result))
        return result

    monkeypatch.setattr(orchestrator, "record_discovery_opportunity", _capture)

    selected, scout_meta = runtime._resolve_autopilot_symbols()  # noqa: SLF001

    assert selected == ()
    assert scout_meta["reason"] == "no_trade_candidates_meet_threshold"
    assert scout_meta["status_counts"]["no_trade"] == 1

    latest_by_symbol = {row["symbol"]: row for row in recorded}
    assert latest_by_symbol["NVDA"]["status"] == "pruned_threshold"
    assert latest_by_symbol["AAPL"]["status"] == "pruned_threshold"
    assert latest_by_symbol["MSFT"]["status"] == "pruned_threshold"
    assert latest_by_symbol["CASH"]["status"] == "no_trade"
    assert latest_by_symbol["CASH"]["metadata"]["discovery_reason"] == "thresholds_not_met"


@pytest.mark.anyio
async def test_runtime_workers_execute_ceo_command_pipeline(monkeypatch):
    bus, _, runtime = _build_stack()
    from app.fund import agent_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "market_session_status",
        lambda _settings: {
            "open": True,
            "trading_day": True,
            "reason": "market_open",
            "source": "test",
            "checked_at": "2026-05-15T14:30:00Z",
            "next_open": None,
            "next_close": "2026-05-15T20:00:00Z",
        },
    )
    monkeypatch.setattr(
        runtime._orchestrator,
        "execute_decision",
        lambda **kwargs: {
            "status": "executed",
            "decision_id": kwargs.get("thesis_id", "decision-test"),
            "risk_id": "risk-test",
            "intent_id": "intent-test",
            "order_id": "order-test",
            "execution": {"status": "executed", "reason": None},
        },
    )
    await runtime.start()
    try:
        enqueued = runtime.enqueue_ceo_command(
            run_id="run-agent-runtime-1",
            agent_id="ceo-1",
            command="research and trade aapl",
            payload={
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 1,
                "price": 100,
                "sleeve": "tactical",
            },
        )
        assert enqueued["role"] == "insight_researcher"

        deadline = monotonic() + 8
        while monotonic() < deadline:
            tasks = bus.list_tasks()
            if any(task.role == "trader" and task.status in {"completed", "blocked"} for task in tasks):
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("trader task did not complete in time")

        status = runtime.status()
        assert status["started"] is True
        researcher = next(item for item in status["workers"] if item["role"] == "insight_researcher")
        trader = next(item for item in status["workers"] if item["role"] == "trader")
        assert researcher["completed_count"] >= 1
        assert trader["completed_count"] + trader["blocked_count"] >= 1
    finally:
        await runtime.stop()


@pytest.mark.anyio
async def test_runtime_autopilot_kick_enqueues_and_executes(monkeypatch):
    bus, orchestrator, runtime = _build_stack()
    from app.fund import agent_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "market_session_status",
        lambda _settings: {
            "open": True,
            "trading_day": True,
            "reason": "market_open",
            "source": "test",
            "checked_at": "2026-05-15T14:30:00Z",
            "next_open": None,
            "next_close": "2026-05-15T20:00:00Z",
        },
    )
    runtime = FundAgentRuntime(
        orchestrator=orchestrator,
        task_bus_service=bus,
        enabled=True,
        poll_interval_seconds=0.05,
        autopilot_enabled=True,
        autopilot_interval_seconds=300,
        autopilot_symbols=("AAPL",),
        autopilot_default_side="buy",
        autopilot_default_quantity=1.0,
    )
    monkeypatch.setattr(
        runtime._orchestrator,
        "execute_decision",
        lambda **kwargs: {
            "status": "executed",
            "decision_id": kwargs.get("thesis_id", "decision-test"),
            "risk_id": "risk-test",
            "intent_id": "intent-test",
            "order_id": "order-test",
            "execution": {"status": "executed", "reason": None},
        },
    )
    await runtime.start()
    try:
        kicked = runtime.kick_autopilot(run_id="run-autopilot-kick-1")
        assert kicked["accepted"] is True
        assert kicked["enqueued_count"] >= 6

        deadline = monotonic() + 8
        while monotonic() < deadline:
            tasks = bus.list_tasks()
            if any(task.role == "trader" and task.status in {"completed", "blocked"} for task in tasks):
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("autopilot trader task did not complete in time")

        status = runtime.status()
        assert status["autopilot"]["cycles"] >= 1
        assert status["autopilot"]["enqueued_count"] >= 6
        assert str(status["autopilot"]["last_run_id"]).startswith("run-autopilot-")
        assert status["autopilot"]["last_run_at"] is not None
    finally:
        await runtime.stop()


@pytest.mark.anyio
async def test_runtime_autopilot_skips_when_market_closed(monkeypatch):
    bus, orchestrator, runtime = _build_stack()
    runtime = FundAgentRuntime(
        orchestrator=orchestrator,
        task_bus_service=bus,
        enabled=True,
        poll_interval_seconds=0.05,
        autopilot_enabled=True,
        autopilot_interval_seconds=300,
        autopilot_symbols=("AAPL",),
        autopilot_dynamic_universe_enabled=False,
        session_guard_enabled=True,
    )

    from app.fund import agent_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "market_session_status",
        lambda _settings: {
            "open": False,
            "trading_day": False,
            "reason": "weekend_or_holiday",
            "source": "test",
            "checked_at": "2026-04-19T00:00:00Z",
        },
    )

    await runtime.start()
    try:
        kicked = runtime.kick_autopilot(run_id="run-autopilot-closed-1")
        assert kicked["accepted"] is True
        assert kicked["enqueued_count"] == 0
        assert kicked["reason"] == "weekend_or_holiday"

        status = runtime.status()
        assert status["autopilot"]["last_error"] == "weekend_or_holiday"
        assert status["autopilot"]["last_session"]["open"] is False
        assert status["autopilot"]["last_scout"]["selected_symbols"] == []
        assert all(task.role != "trader" for task in bus.list_tasks())
    finally:
        await runtime.stop()


@pytest.mark.anyio
async def test_fund_manager_holds_cash_when_conviction_too_low():
    bus, orchestrator, runtime = _build_stack()
    runtime = FundAgentRuntime(
        orchestrator=orchestrator,
        task_bus_service=bus,
        enabled=True,
        poll_interval_seconds=0.05,
        min_trade_conviction=0.90,
        allow_cash_hold=True,
    )

    report = ContractResearchReport(
        run_id="run-hold-cash-1",
        agent_id="insight_researcher_agent",
        asset_universe=("NVDA",),
        summary="Low conviction context.",
        findings=("Signals are weak and contradictory.",),
        confidence=Decimal("0.40"),
    )
    saved = orchestrator.submit_research(report)

    await runtime.start()
    try:
        enqueued = runtime.enqueue_ceo_command(
            run_id="run-hold-cash-1",
            agent_id="ceo-1",
            command="fund manager decide",
            target_role="fund_manager",
            payload={
                "report_ids": [saved["report_id"]],
                "symbol": "NVDA",
                "conviction": 0.40,
                "sleeve": "tactical",
            },
        )
        assert enqueued["role"] == "fund_manager"

        deadline = monotonic() + 5
        hold_event = None
        while monotonic() < deadline:
            for row in bus.history(limit=-1):
                details = row.get("details") or {}
                if (
                    row.get("role") == "fund_manager"
                    and row.get("status") == "completed"
                    and details.get("decision") == "hold_cash"
                ):
                    hold_event = row
                    break
            if hold_event is not None:
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("fund_manager hold_cash decision did not complete in time")

        assert hold_event is not None
        details = hold_event.get("details") or {}
        assert details.get("reason") == "conviction_below_threshold"
        assert float(details.get("conviction") or 0) < 0.90
        assert all(task.role != "trader" for task in bus.list_tasks())
    finally:
        await runtime.stop()


@pytest.mark.anyio
async def test_runtime_uses_ai_role_adapter_when_available(monkeypatch):
    bus, orchestrator, runtime = _build_stack()

    class _StubAdapter:
        def analyze_specialist(self, **kwargs):  # noqa: ANN003
            return AIRoleAnalysis(
                summary="AI adapter summary",
                findings=("AI finding 1", "AI finding 2"),
                confidence=kwargs["fallback_confidence"],
                citations=("ai-src-1",),
                metadata={"used": True, "provider": "stub", "model": "stub-model"},
                provider="stub",
                model="stub-model",
                raw_text='{"summary":"AI adapter summary"}',
            )

        def health(self) -> dict:
            return {"enabled": True, "provider": "stub"}

    from app.fund import agent_runtime as runtime_module

    monkeypatch.setattr(runtime_module, "ai_role_adapter", _StubAdapter())
    await runtime.start()
    try:
        enqueued = runtime.enqueue_ceo_command(
            run_id="run-ai-adapter-1",
            agent_id="ceo-1",
            command="technical analysis on aapl",
            target_role="technical_analyst",
            payload={"symbol": "AAPL", "side": "buy", "quantity": 1, "price": 100},
        )
        assert enqueued["role"] == "technical_analyst"

        deadline = monotonic() + 8
        report_id = None
        while monotonic() < deadline:
            for row in bus.history(limit=-1):
                details = row.get("details") or {}
                if row.get("status") == "completed" and details.get("report_id"):
                    report_id = details.get("report_id")
                    break
            if report_id:
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("analyst task did not complete in time")

        report = orchestrator._reports.get(report_id)  # noqa: SLF001
        assert report is not None
        assert report.summary == "AI adapter summary"
        assert report.findings[0] == "AI finding 1"
    finally:
        await runtime.stop()


@pytest.mark.anyio
async def test_runtime_blog_writer_publishes_from_report(monkeypatch):
    bus, orchestrator, runtime = _build_stack()

    published = []

    class _StubBlogService:
        def publish_from_research(self, *, report, command=None, trigger_source="agent_runtime"):  # noqa: ANN001, ARG002
            report_id = report.get("report_id") if isinstance(report, dict) else report.report_id
            row = {"id": f"blog-{report_id}", "source_report_id": report_id}
            published.append(row)
            return row

    from app.fund import agent_runtime as runtime_module
    monkeypatch.setattr(runtime_module, "blog_service", _StubBlogService())

    report = ContractResearchReport(
        run_id="run-blog-runtime-1",
        agent_id="insight_researcher_agent",
        asset_universe=("AAPL",),
        summary="Insight summary for blog writer validation.",
        findings=("Insight summary for blog writer validation.",),
        confidence=Decimal("0.70"),
    )
    saved = orchestrator.submit_research(report)

    await runtime.start()
    try:
        queued = runtime.enqueue_ceo_command(
            run_id="run-blog-runtime-1",
            command="publish blog now",
            target_role="blog_writer",
            payload={"report_ids": [saved["report_id"]]},
        )
        assert queued["role"] == "blog_writer"

        deadline = monotonic() + 5
        while monotonic() < deadline:
            tasks = bus.list_tasks()
            if any(task.role == "blog_writer" and task.status == "completed" for task in tasks):
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("blog_writer task did not complete in time")

        assert len(published) >= 1
        assert published[0]["source_report_id"] == saved["report_id"]
    finally:
        await runtime.stop()
