from __future__ import annotations

from decimal import Decimal

from app.broker.paper import PaperBroker
from app.fund.audit_log import AuditLog
from app.fund.contracts import ResearchReport as ContractResearchReport
from app.fund.contracts import Sleeve
from app.fund.decision_ledger import DecisionLedger
from app.fund.knowledge_graph import KnowledgeGraph
from app.fund.orchestrator import FirmOrchestrator
from app.fund.research_memory import ResearchMemoryStore
from app.fund.sentiment_ingest import SentimentIngestService
from app.fund.task_bus import TaskBus
import app.fund.orchestrator as orchestrator_module


class _StubPolicyGate:
    def __init__(self, *, approved: bool, reasons: list[str] | None = None) -> None:
        self.approved = approved
        self.reasons = list(reasons or [])
        self.calls: list[tuple[object, list[dict], float]] = []
        self.limits = type("_Limits", (), {"max_order_notional_usd": 1_000_000.0})()

    def evaluate(self, intent, positions: list[dict], equity: float):
        self.calls.append((intent, list(positions), float(equity)))
        return self.approved, list(self.reasons)


class _StubEngineResult:
    def __init__(self, payload: dict) -> None:
        self._payload = dict(payload)

    def to_dict(self) -> dict:
        return dict(self._payload)


def _engine_payload(policy_version: str = "deterministic-policy-v9.9.9") -> dict:
    return {
        "symbol": "AAPL",
        "score": 0.72,
        "confidence": 0.78,
        "subscores": {"sentiment": 0.18},
        "model": {"selected": "meta-intent-v1.0.0"},
        "diagnostics": {
            "technical": {"confidence": 0.74, "volume_ratio": 0.8, "atr_pct": 0.02, "regime_edge": 0.25},
            "sentiment": {"headline_count": 2},
            "meta_intent": {
                "expected_utility": 0.09,
                "reason_codes": ["dominant_technical"],
                "diagnostics": {
                    "sign_consensus": 0.86,
                    "aggregate_uncertainty": 0.21,
                    "domain_disagreement": 0.12,
                },
            },
            "policy": {"safe_mode": False},
            "model_versions": {"policy": policy_version},
        },
    }


def _build_orchestrator(policy_gate: _StubPolicyGate) -> tuple[FirmOrchestrator, AuditLog, DecisionLedger]:
    audit = AuditLog()
    ledger = DecisionLedger()
    orchestrator = FirmOrchestrator(
        task_bus_service=TaskBus(),
        decision_ledger_service=ledger,
        audit_log_service=audit,
        policy_gate_service=policy_gate,
        research_memory_store=ResearchMemoryStore(),
        sentiment_store=SentimentIngestService(),
        broker=PaperBroker(),
        price_lookup=lambda _symbol: 100.0,
        knowledge_graph_service=KnowledgeGraph(enabled=True, persist=False, graphify_sync_enabled=False),
    )
    return orchestrator, audit, ledger


def test_execute_manual_paper_order_uses_core_policy_contract_and_shared_execution_path(monkeypatch):
    policy_gate = _StubPolicyGate(approved=True)
    orchestrator, audit, ledger = _build_orchestrator(policy_gate)

    monkeypatch.setattr(
        orchestrator_module,
        "run_core_engine",
        lambda _symbol: _StubEngineResult(_engine_payload()),
    )

    result = orchestrator.execute_manual_paper_order(
        run_id="run-manual-1",
        agent_id="manual_trader",
        symbol="aapl",
        side="buy",
        quantity=2.0,
        price=100.0,
        external_blocked_reasons=[],
    )

    assert result["approved"] is True
    assert result["status"] == "executed"
    assert result["policy_gate_id"] == "core_engine_policy"
    assert result["policy_version"] == "deterministic-policy-v9.9.9"
    assert isinstance(result["order"], dict)
    assert result["order"]["id"]

    assert len(policy_gate.calls) == 1
    intent, _positions, _equity = policy_gate.calls[0]
    assert intent.metadata["decision_scoring"]["strategy_family"] == "deterministic_ml_firm_engine"

    pre_trade = audit.list_events(event_type="pre_trade.approved", run_id="run-manual-1")
    assert len(pre_trade) == 1
    pre_payload = pre_trade[0].payload
    assert pre_payload["policy_gate_id"] == "core_engine_policy"
    assert pre_payload["policy_version"] == "deterministic-policy-v9.9.9"
    assert pre_payload["decision_scoring"]["strategy_family"] == "deterministic_ml_firm_engine"

    events = ledger.list_events(limit=-1)
    assert any(row.get("event_type") == "execution.processed" for row in events)
    assert any(row.get("event_type") == "paper.order.executed" for row in events)


def test_execute_manual_paper_order_returns_combined_policy_and_breaker_reasons(monkeypatch):
    policy_gate = _StubPolicyGate(approved=False, reasons=["ml_score_below_threshold"])
    orchestrator, audit, ledger = _build_orchestrator(policy_gate)

    monkeypatch.setattr(
        orchestrator_module,
        "run_core_engine",
        lambda _symbol: _StubEngineResult(_engine_payload()),
    )

    result = orchestrator.execute_manual_paper_order(
        run_id="run-manual-2",
        agent_id="manual_trader",
        symbol="aapl",
        side="buy",
        quantity=2.0,
        price=100.0,
        external_blocked_reasons=["risk_engine:limit"],
    )

    assert result["approved"] is False
    assert result["status"] == "blocked"
    assert result["error"] == "ml_score_below_threshold"
    assert result["reasons"] == ["ml_score_below_threshold", "risk_engine:limit"]

    pre_trade = audit.list_events(event_type="pre_trade.rejected", run_id="run-manual-2")
    assert len(pre_trade) == 1
    assert pre_trade[0].payload["blocked_reasons"] == ["ml_score_below_threshold", "risk_engine:limit"]

    events = ledger.list_events(limit=-1)
    assert any(row.get("event_type") == "paper.order.blocked" for row in events)


def test_execute_manual_paper_order_reuses_provided_signal_artifact(monkeypatch):
    policy_gate = _StubPolicyGate(approved=True)
    orchestrator, audit, _ledger = _build_orchestrator(policy_gate)

    def _unexpected_recompute(_symbol: str):
        raise AssertionError("manual execution should reuse provided signal artifact")

    monkeypatch.setattr(orchestrator_module, "run_core_engine", _unexpected_recompute)

    result = orchestrator.execute_manual_paper_order(
        run_id="run-manual-artifact-1",
        agent_id="manual_trader",
        symbol="aapl",
        side="buy",
        quantity=2.0,
        price=100.0,
        external_blocked_reasons=[],
        metadata={
            "deterministic_ml_signal": _engine_payload(policy_version="deterministic-policy-v8.0.0"),
            "signal_artifact_source": "fund_manager_snapshot",
        },
    )

    assert result["approved"] is True
    assert result["policy_version"] == "deterministic-policy-v8.0.0"
    intent, _positions, _equity = policy_gate.calls[0]
    assert intent.metadata["signal_artifact_reused"] is True
    assert intent.metadata["signal_artifact_source"] == "fund_manager_snapshot"

    pre_trade = audit.list_events(event_type="pre_trade.approved", run_id="run-manual-artifact-1")
    assert len(pre_trade) == 1
    assert pre_trade[0].payload["policy_version"] == "deterministic-policy-v8.0.0"


def test_execute_decision_reuses_provided_signal_artifact(monkeypatch):
    policy_gate = _StubPolicyGate(approved=True)
    orchestrator, _audit, _ledger = _build_orchestrator(policy_gate)

    report = ContractResearchReport(
        run_id="run-decision-artifact-1",
        agent_id="insight_researcher_agent",
        asset_universe=("AAPL",),
        summary="AAPL setup",
        findings=("signal stack aligned",),
        confidence=Decimal("0.82"),
    )
    saved = orchestrator.submit_research(report)
    thesis = orchestrator.create_thesis(
        run_id="run-decision-artifact-1",
        agent_id="fund_manager_agent",
        sleeve=Sleeve.TACTICAL,
        report_ids=[saved["report_id"]],
        statement="Execute AAPL thesis",
        conviction=Decimal("0.82"),
    )

    def _unexpected_recompute(_symbol: str):
        raise AssertionError("execution should reuse provided signal artifact")

    monkeypatch.setattr(orchestrator_module, "run_core_engine", _unexpected_recompute)

    result = orchestrator.execute_decision(
        run_id="run-decision-artifact-1",
        agent_id="trader_agent",
        thesis_id=thesis["thesis_id"],
        symbol="AAPL",
        side="buy",
        quantity=1.0,
        price=100.0,
        metadata={
            "deterministic_ml_signal": _engine_payload(policy_version="deterministic-policy-v7.0.0"),
            "signal_artifact_source": "fund_manager_snapshot",
        },
    )

    assert result["status"] == "executed"
    intent, _positions, _equity = policy_gate.calls[0]
    assert intent.metadata["signal_artifact_reused"] is True
    assert intent.metadata["signal_artifact_source"] == "fund_manager_snapshot"
