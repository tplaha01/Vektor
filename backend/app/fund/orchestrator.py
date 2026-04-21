from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from threading import RLock
from typing import Any, Callable

from app.broker.paper import PaperBroker
from app.config import get_settings
from app.core.context import broker as shared_broker
from app.data.market_data import FEED
from app.fund.allocator import (
    SleeveAllocationRequest,
    SleeveWeights,
    allocate_sleeves,
)
from app.fund.audit_log import AuditLog, audit_log
from app.fund.contracts import (
    DecisionRecord,
    ProvenanceRef,
    ResearchReport as ContractResearchReport,
    RiskAssessment,
    SentimentSnapshot as ContractSentimentSnapshot,
    Sleeve,
    TradeThesis,
    make_immutable_id,
)
from app.fund.decision_ledger import DecisionLedger, decision_ledger
from app.fund.execution_adapter import (
    ExecutionIntent as AdapterExecutionIntent,
    PaperExecutionAdapter,
)
from app.fund.knowledge_graph import KnowledgeGraph, knowledge_graph
from app.fund.openclaw_ingest import OpenClawIngestService, openclaw_ingest_service
from app.fund.policy_gate import PolicyGate, policy_gate
from app.fund.realtime_stream import realtime_stream
from app.fund.research_memory import (
    ResearchMemoryStore,
    ResearchProvenance,
    ResearchReport as MemoryResearchReport,
    research_memory,
)
from app.fund.runtime_guard import data_integrity_guard
from app.fund.sentiment_ingest import (
    SentimentIngestService,
    SentimentProvenance,
    SentimentSnapshot,
    sentiment_ingest,
)
from app.fund.task_bus import TaskBus, task_bus

logger = logging.getLogger("alfred.fund")


def _as_utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class FirmOrchestrator:
    """
    Phase-1 orchestration service for paper-first AI-native hedge fund workflows.
    """

    def __init__(
        self,
        *,
        task_bus_service: TaskBus = task_bus,
        decision_ledger_service: DecisionLedger = decision_ledger,
        audit_log_service: AuditLog = audit_log,
        policy_gate_service: PolicyGate = policy_gate,
        openclaw_service: OpenClawIngestService = openclaw_ingest_service,
        research_memory_store: ResearchMemoryStore = research_memory,
        sentiment_store: SentimentIngestService = sentiment_ingest,
        broker: PaperBroker = shared_broker,
        price_lookup: Callable[[str], float] = FEED.price,
        knowledge_graph_service: KnowledgeGraph = knowledge_graph,
    ) -> None:
        self._task_bus = task_bus_service
        self._decision_ledger = decision_ledger_service
        self._audit_log = audit_log_service
        self._policy_gate = policy_gate_service
        self._openclaw = openclaw_service
        self._research_memory = research_memory_store
        self._sentiment_store = sentiment_store
        self._broker = broker
        self._price_lookup = price_lookup
        self._knowledge_graph = knowledge_graph_service
        self._execution_adapter = PaperExecutionAdapter(broker=broker, price_lookup=price_lookup)
        self._policy_version = "phase1.paper.v1"
        self._lock = RLock()
        settings = get_settings()
        self._default_capital_usd = float(settings.FUND_DEFAULT_CAPITAL_USD)
        self._default_reserve_cash_usd = float(settings.FUND_DEFAULT_RESERVE_CASH_USD)
        self._default_sleeve_weights = self._parse_default_sleeve_weights(settings.FUND_DEFAULT_SLEEVE_WEIGHTS)
        self._run_sleeve_allocations: dict[str, dict[str, float]] = {}
        self._run_sleeve_used_notional: dict[str, dict[str, float]] = {}
        self._reports: dict[str, ContractResearchReport] = {}
        self._theses: dict[str, TradeThesis] = {}
        self._risks: dict[str, RiskAssessment] = {}
        self._attach_knowledge_graph_sinks()

    def allocate_sleeves(
        self,
        *,
        run_id: str,
        total_capital_usd: float,
        reserve_cash_usd: float = 0.0,
        decision_id: str | None = None,
        target_weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        weights = target_weights or {"long_term": 0.5, "recurring": 0.3, "tactical": 0.2}
        req = SleeveAllocationRequest(
            run_id=run_id,
            decision_id=decision_id,
            total_capital_usd=Decimal(str(total_capital_usd)),
            reserve_cash_usd=Decimal(str(reserve_cash_usd)),
            target_weights=SleeveWeights(
                long_term=Decimal(str(weights.get("long_term", 0.5))),
                recurring=Decimal(str(weights.get("recurring", 0.3))),
                tactical=Decimal(str(weights.get("tactical", 0.2))),
            ),
        )
        result = allocate_sleeves(req)
        payload = result.model_dump(mode="json")
        self._register_run_budget_from_allocation(run_id=run_id, allocation=payload)
        self._log_event(
            "allocator.completed",
            run_id=run_id,
            decision_id=decision_id,
            payload={
                "allocation_id": payload["allocation_id"],
                "allocatable_capital_usd": payload["allocatable_capital_usd"],
            },
        )
        return payload

    def submit_research(self, report: ContractResearchReport | dict[str, Any]) -> dict[str, Any]:
        model = report if isinstance(report, ContractResearchReport) else ContractResearchReport.model_validate(report)
        with self._lock:
            self._reports[model.report_id] = model

        memory_report = MemoryResearchReport(
            report_id=model.report_id,
            agent_id=model.agent_id,
            created_at=_as_utc_datetime(model.created_at),
            assets=list(model.asset_universe),
            title=f"Report {model.report_id}",
            summary=model.summary,
            thesis=model.summary,
            confidence=float(model.confidence),
            provenance=[
                ResearchProvenance(
                    source=ref.source_type,
                    confidence=float(model.confidence),
                    external_id=ref.source_id,
                )
                for ref in model.provenance
            ],
            tags=["research"],
            metadata={"run_id": model.run_id},
        )
        self._research_memory.add_report(memory_report)
        task = self._task_bus.create_task(
            run_id=model.run_id,
            agent_id=model.agent_id,
            role="researcher",
            payload={"report_id": model.report_id},
            priority=6,
        )
        self._task_bus.set_status(task.task_id, "completed", {"report_id": model.report_id})
        self._audit_log.record(
            "research.report.ingested",
            {
                "run_id": model.run_id,
                "agent_id": model.agent_id,
                "research_id": model.report_id,
                "assets": list(model.asset_universe),
            },
        )
        self._log_event(
            "research.ingested",
            run_id=model.run_id,
            agent_id=model.agent_id,
            decision_id=None,
            payload={"report_id": model.report_id},
        )
        return model.model_dump(mode="json")

    def create_thesis(
        self,
        *,
        run_id: str,
        agent_id: str,
        sleeve: Sleeve,
        report_ids: list[str],
        statement: str,
        conviction: Decimal,
    ) -> dict[str, Any]:
        for report_id in report_ids:
            if report_id not in self._reports:
                raise ValueError(f"unknown_report_id:{report_id}")

        thesis_id = make_immutable_id(
            "thesis",
            run_id,
            agent_id,
            sleeve.value,
            ",".join(sorted(report_ids)),
            statement,
            conviction,
        )
        thesis = TradeThesis(
            thesis_id=thesis_id,
            run_id=run_id,
            agent_id=agent_id,
            sleeve=sleeve,
            report_ids=tuple(report_ids),
            statement=statement,
            conviction=conviction,
        )
        with self._lock:
            self._theses[thesis.thesis_id] = thesis

        task = self._task_bus.create_task(
            run_id=run_id,
            agent_id=agent_id,
            role="fund_manager",
            payload={"thesis_id": thesis.thesis_id, "report_ids": report_ids},
            priority=7,
        )
        self._task_bus.set_status(task.task_id, "completed", {"thesis_id": thesis.thesis_id})
        self._audit_log.record(
            "thesis.created",
            {
                "run_id": run_id,
                "agent_id": agent_id,
                "thesis_id": thesis.thesis_id,
                "report_ids": report_ids,
                "sleeve": sleeve.value,
            },
        )
        self._log_event(
            "thesis.created",
            run_id=run_id,
            agent_id=agent_id,
            decision_id=None,
            payload={"thesis_id": thesis.thesis_id},
        )
        return thesis.model_dump(mode="json")

    def submit_sentiment(self, snapshot: ContractSentimentSnapshot | dict[str, Any]) -> dict[str, Any]:
        model = (
            snapshot
            if isinstance(snapshot, ContractSentimentSnapshot)
            else ContractSentimentSnapshot.model_validate(snapshot)
        )
        self._sentiment_store.ingest(
            SentimentSnapshot(
                snapshot_id=model.snapshot_id,
                asset=model.symbol,
                channel=model.source,
                text=f"{model.source}:{model.symbol}",
                sentiment_score=float(model.sentiment_score),
                model_name="phase1.sentiment",
                provenance=SentimentProvenance(
                    source=model.source,
                    confidence=float(model.confidence),
                    source_url=model.provenance_url,
                ),
                metadata={"run_id": model.run_id, "agent_id": model.agent_id},
            )
        )
        self._audit_log.record(
            "sentiment.ingested",
            {
                "run_id": model.run_id,
                "agent_id": model.agent_id,
                "symbol": model.symbol,
                "snapshot_id": model.snapshot_id,
            },
        )
        self._log_event(
            "sentiment.ingested",
            run_id=model.run_id,
            agent_id=model.agent_id,
            decision_id=None,
            payload={"snapshot_id": model.snapshot_id, "symbol": model.symbol},
        )
        return model.model_dump(mode="json")

    def execute_decision(
        self,
        *,
        run_id: str,
        agent_id: str,
        thesis_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        thesis = self._theses.get(thesis_id)
        if thesis is None:
            raise ValueError(f"unknown_thesis_id:{thesis_id}")

        normalized_symbol = symbol.upper().strip()
        normalized_side = side.lower().strip()
        decision_id = make_immutable_id(
            "decision",
            run_id,
            thesis_id,
            normalized_symbol,
            normalized_side,
            quantity,
            price if price is not None else "market",
        )
        intent_id = make_immutable_id(
            "intent",
            decision_id,
            normalized_symbol,
            normalized_side,
            quantity,
            price if price is not None else "market",
        )
        data_id = make_immutable_id("data", run_id, thesis_id, normalized_symbol)
        research_id = make_immutable_id("research", run_id, ",".join(sorted(thesis.report_ids)))
        risk_id = make_immutable_id("risk", decision_id, self._policy_version)

        provenance = [ProvenanceRef(source_type="thesis", source_id=thesis_id)]
        provenance.extend(
            ProvenanceRef(source_type="research", source_id=report_id)
            for report_id in thesis.report_ids
        )
        decision = DecisionRecord(
            decision_id=decision_id,
            run_id=run_id,
            agent_id=agent_id,
            sleeve=thesis.sleeve,
            thesis_id=thesis_id,
            risk_id=risk_id,
            intent_id=intent_id,
            status="proposed",
            provenance=tuple(provenance),
        )
        self._decision_ledger.add_decision(decision)

        if data_integrity_guard.halted():
            halt_reason = data_integrity_guard.halt_reason() or "system_halted"
            reasons = [halt_reason]
            self._decision_ledger.update_status(decision_id, "blocked", {"reasons": reasons})
            self._decision_ledger.add_event(
                event_type="execution.blocked",
                decision_id=decision_id,
                order_id=None,
                payload={"reasons": reasons, "risk_id": risk_id, "intent_id": intent_id},
            )
            self._audit_log.record_pre_trade_decision(
                approved=False,
                run_id=run_id,
                decision_id=decision_id,
                agent_id=agent_id,
                blocked_reasons=reasons,
                policy_gate_id=self._policy_version,
                policy_version=self._policy_version,
                research_id=research_id,
                thesis_id=thesis_id,
                metadata={
                    "intent_id": intent_id,
                    "risk_id": risk_id,
                    "symbol": normalized_symbol,
                    "side": normalized_side,
                    "quantity": quantity,
                },
            )
            self._log_event(
                "decision.blocked",
                run_id=run_id,
                agent_id=agent_id,
                decision_id=decision_id,
                payload={"reasons": reasons, "halted": True},
            )
            return {
                "status": "blocked",
                "decision_id": decision_id,
                "risk_id": risk_id,
                "intent_id": intent_id,
                "reasons": reasons,
            }

        trader_task = self._task_bus.create_task(
            run_id=run_id,
            agent_id=agent_id,
            role="trader",
            payload={
                "decision_id": decision_id,
                "thesis_id": thesis_id,
                "symbol": normalized_symbol,
                "side": normalized_side,
            },
            priority=8,
        )
        self._task_bus.set_status(trader_task.task_id, "running", {"decision_id": decision_id})

        effective_price = price if price is not None else float(self._price_lookup(normalized_symbol))
        estimated_notional = float(quantity) * float(effective_price)
        budget_state = self._ensure_run_sleeve_budget(run_id=run_id, sleeve=thesis.sleeve)
        positions = self._broker.list_positions(self._price_lookup)
        equity = self._current_equity(positions)
        intent = AdapterExecutionIntent(
            symbol=normalized_symbol,
            side=normalized_side,
            quantity=float(quantity),
            approved=True,
            decision_id=decision_id,
            risk_id=risk_id,
            intent_id=intent_id,
            data_id=data_id,
            research_id=research_id,
            thesis_id=thesis_id,
            run_id=run_id,
            agent_id=agent_id,
            sleeve=thesis.sleeve.value,
            broker_mode="paper",
            price=float(effective_price),
            metadata={
                "available_cash": self._broker.cash,
                "sleeve_budget_allocated_usd": budget_state["allocated_usd"],
                "sleeve_budget_used_usd": budget_state["used_usd"],
                "sleeve_budget_remaining_usd": budget_state["remaining_usd"],
                "estimated_notional_usd": estimated_notional,
                **(metadata or {}),
            },
        )
        approved, reasons = self._policy_gate.evaluate(intent, positions, equity)
        risk_assessment = RiskAssessment(
            risk_id=risk_id,
            decision_id=decision_id,
            agent_id="risk_auditor",
            policy_version=self._policy_version,
            approved=approved,
            reasons=tuple(reasons),
            max_notional_usd=Decimal(str(self._policy_gate.limits.max_order_notional_usd)),
        )
        with self._lock:
            self._risks[risk_id] = risk_assessment

        self._audit_log.record_pre_trade_decision(
            approved=approved,
            run_id=run_id,
            decision_id=decision_id,
            agent_id=agent_id,
            blocked_reasons=reasons,
            policy_gate_id=self._policy_version,
            policy_version=self._policy_version,
            research_id=research_id,
            thesis_id=thesis_id,
            metadata={
                "intent_id": intent_id,
                "risk_id": risk_id,
                "symbol": normalized_symbol,
                "side": normalized_side,
                "quantity": quantity,
            },
        )
        if not approved:
            self._decision_ledger.update_status(decision_id, "blocked", {"reasons": list(reasons)})
            self._decision_ledger.add_event(
                event_type="execution.blocked",
                decision_id=decision_id,
                order_id=None,
                payload={"reasons": list(reasons), "risk_id": risk_id, "intent_id": intent_id},
            )
            self._task_bus.set_status(
                trader_task.task_id,
                "blocked",
                {"decision_id": decision_id, "reasons": list(reasons)},
            )
            self._log_event(
                "decision.blocked",
                run_id=run_id,
                agent_id=agent_id,
                decision_id=decision_id,
                payload={"reasons": list(reasons), "sleeve_budget": budget_state},
            )
            return {
                "status": "blocked",
                "decision_id": decision_id,
                "risk_id": risk_id,
                "intent_id": intent_id,
                "reasons": list(reasons),
            }

        self._decision_ledger.update_status(decision_id, "approved", {"risk_id": risk_id, "intent_id": intent_id})
        execution_result = self._execution_adapter.execute(intent)
        order_id = (execution_result.get("order") or {}).get("id")
        execution_status = execution_result.get("status")
        if execution_status == "executed":
            self._update_run_sleeve_used_notional(
                run_id=run_id,
                sleeve=thesis.sleeve,
                side=normalized_side,
                quantity=float((execution_result.get("order") or {}).get("quantity") or quantity),
                price=float((execution_result.get("order") or {}).get("avg_price") or effective_price),
            )

        if execution_status == "executed":
            decision_status = "executed"
            self._task_bus.set_status(trader_task.task_id, "completed", {"order_id": order_id})
        else:
            decision_status = "blocked"
            self._task_bus.set_status(
                trader_task.task_id,
                "blocked",
                {"decision_id": decision_id, "reason": execution_result.get("reason")},
            )

        self._decision_ledger.update_status(
            decision_id,
            decision_status,
            {"order_id": order_id, "execution_status": execution_status},
        )
        self._decision_ledger.add_event(
            event_type="execution.processed",
            decision_id=decision_id,
            order_id=order_id,
            payload=execution_result,
        )
        self._audit_log.record(
            "execution.intent.processed",
            {
                "run_id": run_id,
                "decision_id": decision_id,
                "risk_id": risk_id,
                "intent_id": intent_id,
                "order_id": order_id,
                "status": execution_status,
                "reason": execution_result.get("reason"),
            },
        )
        self._log_event(
            "decision.executed" if execution_status == "executed" else "decision.execution_rejected",
            run_id=run_id,
            agent_id=agent_id,
            decision_id=decision_id,
            payload={
                "order_id": order_id,
                "execution_status": execution_status,
                "sleeve_budget": self._ensure_run_sleeve_budget(run_id=run_id, sleeve=thesis.sleeve),
            },
        )
        return {
            "status": execution_status,
            "decision_id": decision_id,
            "risk_id": risk_id,
            "intent_id": intent_id,
            "order_id": order_id,
            "execution": execution_result,
        }

    def list_active_tasks(self) -> list[dict[str, Any]]:
        return [task.model_dump(mode="json") for task in self._task_bus.active_tasks()]

    def get_research_report(self, report_id: str) -> dict[str, Any] | None:
        key = str(report_id or "").strip()
        if not key:
            return None
        with self._lock:
            report = self._reports.get(key)
        if report is not None:
            return report.model_dump(mode="json")
        memory_report = self._research_memory.get(key)
        if memory_report is None:
            return None
        return {
            "report_id": memory_report.report_id,
            "run_id": memory_report.metadata.get("run_id"),
            "agent_id": memory_report.agent_id,
            "created_at": memory_report.created_at.isoformat(),
            "asset_universe": list(memory_report.assets),
            "summary": memory_report.summary,
            "findings": [memory_report.summary, *([memory_report.thesis] if memory_report.thesis else [])],
            "confidence": memory_report.confidence,
            "provenance": [
                {"source_type": "research", "source_id": str(item.external_id or item.source)}
                for item in memory_report.provenance
            ],
        }

    def list_recent_research_reports(
        self,
        *,
        limit: int = 20,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_symbol = str(symbol or "").strip().upper()
        if normalized_symbol:
            rows = self._research_memory.get_by_asset(normalized_symbol, limit=max(1, int(limit)))
        else:
            rows = self._research_memory.list_all(limit=max(1, int(limit)))
        return [
            {
                "report_id": row.report_id,
                "run_id": row.metadata.get("run_id"),
                "agent_id": row.agent_id,
                "created_at": row.created_at.isoformat(),
                "asset_universe": list(row.assets),
                "summary": row.summary,
                "findings": [row.summary, *([row.thesis] if row.thesis else [])],
                "confidence": row.confidence,
                "provenance": [
                    {"source_type": "research", "source_id": str(item.external_id or item.source)}
                    for item in row.provenance
                ],
            }
            for row in rows
        ]

    def list_task_history(
        self,
        *,
        limit: int = 200,
        run_id: str | None = None,
        agent_id: str | None = None,
        role: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._task_bus.query_history(
            limit=limit,
            run_id=run_id,
            agent_id=agent_id,
            role=role,
            status=status,
        )

    def list_pending_decisions(self) -> list[dict[str, Any]]:
        return [row.model_dump(mode="json") for row in self._decision_ledger.pending_decisions()]

    def list_blocked_trades(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._audit_log.list_blocked(limit=limit)

    def audit_timeline_for_order(self, order_id: str) -> list[dict[str, Any]]:
        ledger_events = self._decision_ledger.timeline_for_order(order_id)
        audit_events = self._audit_log.query_by_order(order_id)
        combined = []
        for row in ledger_events:
            combined.append(
                {
                    "source": "decision_ledger",
                    "event_id": row.get("event_id"),
                    "event_type": row.get("event_type"),
                    "timestamp": row.get("ts"),
                    "payload": row.get("payload", {}),
                }
            )
        for row in audit_events:
            combined.append(
                {
                    "source": "audit_log",
                    "event_id": row.get("event_id"),
                    "event_type": row.get("event_type"),
                    "timestamp": row.get("event_ts"),
                    "payload": row.get("payload", {}),
                }
            )
        combined.sort(key=lambda item: item.get("timestamp") or "")
        return combined

    def ingest_openclaw(self, *, kind: str, payload: dict[str, Any], token: str) -> dict[str, Any]:
        result = self._openclaw.ingest(kind=kind, payload=payload, token=token)
        self._log_event(
            "openclaw.ingest",
            run_id=payload.get("run_id"),
            agent_id=payload.get("agent_id"),
            decision_id=payload.get("decision_id"),
            payload={"kind": kind, "accepted": result.get("accepted")},
        )
        return result

    def openclaw_health(self) -> dict[str, Any]:
        return self._openclaw.health()

    def openclaw_rejections(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._openclaw.list_rejected(limit=limit)

    def list_knowledge_events(
        self,
        *,
        limit: int = 200,
        namespace: str | None = None,
        source: str | None = None,
        event_type: str | None = None,
        run_id: str | None = None,
        agent_id: str | None = None,
        decision_id: str | None = None,
        order_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._knowledge_graph.list_events(
            limit=limit,
            namespace=namespace,
            source=source,
            event_type=event_type,
            run_id=run_id,
            agent_id=agent_id,
            decision_id=decision_id,
            order_id=order_id,
        )

    def knowledge_lineage(
        self,
        *,
        run_id: str | None = None,
        decision_id: str | None = None,
        order_id: str | None = None,
        report_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self._knowledge_graph.lineage(
            run_id=run_id,
            decision_id=decision_id,
            order_id=order_id,
            report_id=report_id,
            limit=limit,
        )

    def knowledge_stats(self) -> dict[str, Any]:
        return self._knowledge_graph.stats()

    def ingest_development_log(
        self,
        *,
        entry_id: str,
        stage: str,
        actor_name: str,
        actor_platform: str,
        actor_model: str,
        actor_provider: str | None = None,
        run_id: str | None = None,
        branch: str | None = None,
        commit_start: str | None = None,
        commit_end: str | None = None,
        scope: str = "",
        files: list[str] | None = None,
        validation: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_stage = str(stage or "update").strip().lower()
        event_type = f"development.devlog.{normalized_stage}"
        payload = {
            "entry_id": entry_id,
            "stage": normalized_stage,
            "actor_name": actor_name,
            "actor_platform": actor_platform,
            "actor_model": actor_model,
            "actor_provider": actor_provider,
            "git_branch": branch,
            "git_commit_start": commit_start,
            "git_commit_end": commit_end,
            "scope": scope,
            "files": list(files or []),
            "validation": validation,
            "notes": notes,
            "metadata": dict(metadata or {}),
        }
        event = self._knowledge_graph.ingest(
            source="development",
            event_type=event_type,
            source_event_id=entry_id,
            run_id=run_id,
            agent_id=actor_name,
            payload=payload,
        )
        self._publish_realtime("development", event)
        return {"accepted": True, "event": event}

    def reset_knowledge_graph(
        self,
        *,
        run_id: str | None = None,
        agent_id: str = "ceo",
        seed_event: bool = True,
    ) -> dict[str, Any]:
        reset_result = self._knowledge_graph.reset(clear_storage=True)
        seeded_event = None
        if seed_event:
            seeded_event = self._knowledge_graph.ingest(
                source="development",
                event_type="development.kb_reset",
                run_id=run_id,
                agent_id=agent_id,
                payload={"reset_result": reset_result},
            )
            self._publish_realtime("development", seeded_event)
        return {
            "reset_result": reset_result,
            "seeded_event": seeded_event,
            "stats": self._knowledge_graph.stats(),
        }

    def rebuild_knowledge_projection(
        self,
        *,
        run_id: str | None = None,
        agent_id: str = "ceo",
        seed_event: bool = True,
    ) -> dict[str, Any]:
        rebuild_result = self._knowledge_graph.rebuild_projection()
        seeded_event = None
        if seed_event:
            seeded_event = self._knowledge_graph.ingest(
                source="development",
                event_type="development.kb_projection_rebuilt",
                run_id=run_id,
                agent_id=agent_id,
                payload={"rebuild_result": rebuild_result},
            )
            self._publish_realtime("development", seeded_event)
        return {
            "rebuild_result": rebuild_result,
            "seeded_event": seeded_event,
            "stats": self._knowledge_graph.stats(),
        }

    def sleeve_budget_status(self, run_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            run_ids = [run_id] if run_id else list(self._run_sleeve_allocations.keys())

        budgets: list[dict[str, Any]] = []
        for candidate_run_id in run_ids:
            if not candidate_run_id:
                continue
            allocation = self._run_sleeve_allocations.get(candidate_run_id) or {}
            used = self._run_sleeve_used_notional.get(candidate_run_id) or {}
            sleeve_rows: dict[str, dict[str, float]] = {}
            for sleeve_name in ("long_term", "recurring", "tactical"):
                allocated = float(allocation.get(sleeve_name, 0.0))
                used_amount = float(used.get(sleeve_name, 0.0))
                sleeve_rows[sleeve_name] = {
                    "allocated_usd": round(allocated, 2),
                    "used_usd": round(used_amount, 2),
                    "remaining_usd": round(max(0.0, allocated - used_amount), 2),
                }
            budgets.append({"run_id": candidate_run_id, "sleeves": sleeve_rows})

        return {
            "configured_defaults": {
                "total_capital_usd": self._default_capital_usd,
                "reserve_cash_usd": self._default_reserve_cash_usd,
                "weights": dict(self._default_sleeve_weights),
            },
            "runs": budgets,
        }

    def _current_equity(self, positions: list[dict[str, Any]]) -> float:
        market_value = 0.0
        for pos in positions:
            mv = float(pos.get("market_value") or 0.0)
            if mv <= 0:
                qty = float(pos.get("qty") or 0.0)
                px = float(pos.get("market_price") or self._price_lookup(str(pos.get("symbol", ""))))
                mv = qty * px
            market_value += mv
        return float(self._broker.cash) + market_value

    def _parse_default_sleeve_weights(self, raw: str | None) -> dict[str, float]:
        defaults = {"long_term": 0.5, "recurring": 0.3, "tactical": 0.2}
        if not raw:
            return defaults
        parsed: dict[str, float] = {}
        for item in str(raw).split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            normalized_key = key.strip().lower()
            if normalized_key not in defaults:
                continue
            try:
                parsed[normalized_key] = float(value.strip())
            except ValueError:
                continue
        merged = {**defaults, **parsed}
        total = sum(max(0.0, amount) for amount in merged.values())
        if total <= 0:
            return defaults
        return {key: max(0.0, amount) / total for key, amount in merged.items()}

    def _register_run_budget_from_allocation(self, *, run_id: str, allocation: dict[str, Any]) -> None:
        lines = allocation.get("lines") if isinstance(allocation, dict) else []
        normalized_alloc: dict[str, float] = {}
        if isinstance(lines, list):
            for line in lines:
                if not isinstance(line, dict):
                    continue
                sleeve_name = str(line.get("sleeve") or "").strip().lower()
                if sleeve_name not in {"long_term", "recurring", "tactical"}:
                    continue
                normalized_alloc[sleeve_name] = float(line.get("amount_usd") or 0.0)

        with self._lock:
            self._run_sleeve_allocations[run_id] = {
                "long_term": float(normalized_alloc.get("long_term", 0.0)),
                "recurring": float(normalized_alloc.get("recurring", 0.0)),
                "tactical": float(normalized_alloc.get("tactical", 0.0)),
            }
            existing_used = self._run_sleeve_used_notional.get(run_id, {})
            self._run_sleeve_used_notional[run_id] = {
                "long_term": float(existing_used.get("long_term", 0.0)),
                "recurring": float(existing_used.get("recurring", 0.0)),
                "tactical": float(existing_used.get("tactical", 0.0)),
            }

    def _ensure_run_budget_initialized(self, run_id: str) -> None:
        with self._lock:
            if run_id in self._run_sleeve_allocations:
                return
        allocation = self.allocate_sleeves(
            run_id=run_id,
            total_capital_usd=self._default_capital_usd,
            reserve_cash_usd=self._default_reserve_cash_usd,
            decision_id=make_immutable_id("budget", run_id),
            target_weights=self._default_sleeve_weights,
        )
        self._log_event(
            "sleeve_budget.initialized",
            run_id=run_id,
            payload={"allocation_id": allocation.get("allocation_id"), "weights": dict(self._default_sleeve_weights)},
        )

    def _ensure_run_sleeve_budget(self, *, run_id: str, sleeve: Sleeve) -> dict[str, float]:
        self._ensure_run_budget_initialized(run_id)
        sleeve_name = sleeve.value
        with self._lock:
            allocation = self._run_sleeve_allocations.get(run_id, {})
            used = self._run_sleeve_used_notional.get(run_id, {})
            allocated_usd = float(allocation.get(sleeve_name, 0.0))
            used_usd = float(used.get(sleeve_name, 0.0))
        remaining = max(0.0, allocated_usd - used_usd)
        return {
            "sleeve": sleeve_name,
            "allocated_usd": round(allocated_usd, 2),
            "used_usd": round(used_usd, 2),
            "remaining_usd": round(remaining, 2),
        }

    def _update_run_sleeve_used_notional(
        self,
        *,
        run_id: str,
        sleeve: Sleeve,
        side: str,
        quantity: float,
        price: float,
    ) -> None:
        notional = max(0.0, float(quantity) * float(price))
        sleeve_name = sleeve.value
        with self._lock:
            current = self._run_sleeve_used_notional.setdefault(
                run_id,
                {"long_term": 0.0, "recurring": 0.0, "tactical": 0.0},
            )
            previous = float(current.get(sleeve_name, 0.0))
            if side == "sell":
                current[sleeve_name] = max(0.0, previous - notional)
            else:
                current[sleeve_name] = previous + notional

    def _log_event(
        self,
        event_type: str,
        *,
        run_id: str | None,
        agent_id: str | None = None,
        decision_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        body = {
            "event_type": event_type,
            "run_id": run_id,
            "agent_id": agent_id,
            "decision_id": decision_id,
            "payload": payload or {},
        }
        logger.info(json.dumps(body, sort_keys=True))
        event = self._knowledge_graph.ingest(
            source="orchestrator",
            event_type=event_type,
            run_id=run_id,
            agent_id=agent_id,
            decision_id=decision_id,
            payload=payload or {},
        )
        self._publish_realtime("orchestrator", event)

    def _attach_knowledge_graph_sinks(self) -> None:
        self._task_bus.set_event_sink(lambda event: self._capture_knowledge_event("task_bus", event))
        self._decision_ledger.set_event_sink(lambda event: self._capture_knowledge_event("decision_ledger", event))
        self._audit_log.set_event_sink(lambda event: self._capture_knowledge_event("audit_log", event))
        self._research_memory.set_event_sink(lambda event: self._capture_knowledge_event("research_memory", event))
        self._sentiment_store.set_event_sink(lambda event: self._capture_knowledge_event("sentiment_ingest", event))
        self._openclaw.set_event_sink(lambda event: self._capture_knowledge_event("openclaw_ingest", event))
        self._backfill_knowledge_graph()

    def _capture_knowledge_event(self, source: str, event: dict[str, Any]) -> None:
        captured = self._knowledge_graph.capture(source, event)
        self._publish_realtime(source, captured)

    def _publish_realtime(self, source: str, event: dict[str, Any] | None) -> None:
        if not isinstance(event, dict):
            return
        try:
            realtime_stream.publish(source=source, event=event)
        except Exception:
            pass

    def _backfill_knowledge_graph(self) -> None:
        for row in self._task_bus.history(limit=-1):
            self._knowledge_graph.capture(
                "task_bus",
                {
                    "event_id": f"{row.get('task_id')}:{row.get('event')}:{row.get('status')}:{row.get('ts')}",
                    "event_type": f"task_bus.{row.get('event')}",
                    "ts": row.get("ts"),
                    "payload": row,
                },
            )
        for row in self._decision_ledger.list_events(limit=-1):
            self._knowledge_graph.capture("decision_ledger", row)
        for row in self._audit_log.list_events(limit=-1):
            self._knowledge_graph.capture("audit_log", row.to_dict())
        for report in self._research_memory.list_all(limit=None):
            self._knowledge_graph.capture(
                "research_memory",
                {
                    "event_id": report.report_id,
                    "event_type": "research.report.stored",
                    "created_at": report.created_at.isoformat(),
                    "run_id": report.metadata.get("run_id"),
                    "agent_id": report.agent_id,
                    "payload": report.model_dump(mode="json"),
                },
            )
        for snapshot in self._sentiment_store.list_recent(limit=10_000):
            self._knowledge_graph.capture(
                "sentiment_ingest",
                {
                    "event_id": snapshot.snapshot_id,
                    "event_type": "sentiment.snapshot.stored",
                    "created_at": snapshot.created_at.isoformat(),
                    "run_id": snapshot.metadata.get("run_id"),
                    "agent_id": snapshot.metadata.get("agent_id"),
                    "payload": snapshot.model_dump(mode="json"),
                },
            )
        for row in self._openclaw.list_accepted(limit=10_000):
            self._knowledge_graph.capture(
                "openclaw_ingest",
                {
                    "event_id": row.get("ingest_id"),
                    "event_type": "openclaw.ingest.accepted",
                    "received_at": row.get("received_at"),
                    "run_id": (row.get("payload") or {}).get("run_id"),
                    "agent_id": (row.get("payload") or {}).get("agent_id"),
                    "decision_id": (row.get("payload") or {}).get("decision_id"),
                    "payload": row,
                },
            )
        for row in self._openclaw.list_rejected(limit=10_000):
            self._knowledge_graph.capture(
                "openclaw_ingest",
                {
                    "event_id": row.get("reject_id"),
                    "event_type": "openclaw.ingest.rejected",
                    "received_at": row.get("received_at"),
                    "run_id": (row.get("payload") or {}).get("run_id"),
                    "agent_id": (row.get("payload") or {}).get("agent_id"),
                    "decision_id": (row.get("payload") or {}).get("decision_id"),
                    "payload": row,
                },
            )


firm_orchestrator = FirmOrchestrator()
