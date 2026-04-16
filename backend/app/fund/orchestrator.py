from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from threading import RLock
from typing import Any, Callable

from app.broker.paper import PaperBroker
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
from app.fund.openclaw_ingest import OpenClawIngestService, openclaw_ingest_service
from app.fund.policy_gate import PolicyGate, policy_gate
from app.fund.research_memory import (
    ResearchMemoryStore,
    ResearchProvenance,
    ResearchReport as MemoryResearchReport,
    research_memory,
)
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
        self._execution_adapter = PaperExecutionAdapter(broker=broker, price_lookup=price_lookup)
        self._policy_version = "phase1.paper.v1"
        self._lock = RLock()
        self._reports: dict[str, ContractResearchReport] = {}
        self._theses: dict[str, TradeThesis] = {}
        self._risks: dict[str, RiskAssessment] = {}

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
            metadata={"available_cash": self._broker.cash, **(metadata or {})},
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
                payload={"reasons": list(reasons)},
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
            payload={"order_id": order_id, "execution_status": execution_status},
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


firm_orchestrator = FirmOrchestrator()
