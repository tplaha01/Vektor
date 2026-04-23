from __future__ import annotations

import json
import logging
from dataclasses import asdict
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
from app.fund.allocation_policy import (
    build_default_policy,
    infer_asset_class,
    infer_instrument_type,
    infer_routing_mode,
    infer_underlier_symbol,
    normalize_asset_class,
)
from app.fund.approval_center import ApprovalCenter, approval_center
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
from app.fund.policy_gate import (
    PolicyGate,
    build_portfolio_threshold_context,
    policy_gate,
    resolve_decision_gate_thresholds,
)
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
from app.storage import db as storage_db

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
        approval_center_service: ApprovalCenter = approval_center,
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
        self._approval_center = approval_center_service
        self._execution_adapter = PaperExecutionAdapter(broker=broker, price_lookup=price_lookup)
        self._policy_version = "phase1.paper.v1"
        self._lock = RLock()
        self._settings = get_settings()
        self._broker_mode = str(self._settings.BROKER or "paper").strip().lower() or "paper"
        self._require_trade_approval = bool(self._settings.CEO_APPROVAL_REQUIRED_FOR_TRADES)
        self._require_allocation_approval = bool(self._settings.CEO_APPROVAL_REQUIRED_FOR_ALLOCATION_CHANGES)
        self._require_major_reroute_approval = bool(self._settings.CEO_APPROVAL_REQUIRED_FOR_MAJOR_REROUTES)
        self._default_capital_usd = float(self._settings.FUND_DEFAULT_CAPITAL_USD)
        self._default_reserve_cash_usd = float(self._settings.FUND_DEFAULT_RESERVE_CASH_USD)
        self._default_sleeve_weights = self._parse_default_sleeve_weights(self._settings.FUND_DEFAULT_SLEEVE_WEIGHTS)
        self._run_sleeve_allocations: dict[str, dict[str, float]] = {}
        self._run_sleeve_used_notional: dict[str, dict[str, float]] = {}
        self._run_asset_class_used_notional: dict[str, dict[str, float]] = {}
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

    def set_allocation_policy(
        self,
        *,
        run_id: str,
        agent_id: str,
        total_capital_usd: float | None = None,
        reserve_cash_usd: float | None = None,
        asset_weights: dict[str, Any] | None = None,
        sleeve_weights: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._require_allocation_approval:
            return self.request_allocation_policy_change(
                run_id=run_id,
                agent_id=agent_id,
                total_capital_usd=total_capital_usd,
                reserve_cash_usd=reserve_cash_usd,
                asset_weights=asset_weights,
                sleeve_weights=sleeve_weights,
                constraints=constraints,
                metadata=metadata,
            )
        return self._apply_allocation_policy(
            run_id=run_id,
            agent_id=agent_id,
            total_capital_usd=total_capital_usd,
            reserve_cash_usd=reserve_cash_usd,
            asset_weights=asset_weights,
            sleeve_weights=sleeve_weights,
            constraints=constraints,
            metadata=metadata,
        )

    def request_allocation_policy_change(
        self,
        *,
        run_id: str,
        agent_id: str,
        total_capital_usd: float | None = None,
        reserve_cash_usd: float | None = None,
        asset_weights: dict[str, Any] | None = None,
        sleeve_weights: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        latest = self.get_allocation_policy(run_id=run_id)
        total = float(total_capital_usd if total_capital_usd is not None else latest.get("total_capital_usd") or self._default_capital_usd)
        reserve = float(reserve_cash_usd if reserve_cash_usd is not None else latest.get("reserve_cash_usd") or self._default_reserve_cash_usd)
        merged_asset_weights = dict(latest.get("asset_weights") or {})
        merged_asset_weights.update(dict(asset_weights or {}))
        merged_sleeve_weights = dict(latest.get("sleeve_weights") or {})
        merged_sleeve_weights.update(dict(sleeve_weights or {}))
        merged_constraints = dict(latest.get("constraints") or {})
        merged_constraints.update(dict(constraints or {}))
        merged_metadata = dict(latest.get("metadata") or {})
        merged_metadata.update(dict(metadata or {}))
        preview_policy = build_default_policy(
            run_id=run_id,
            total_capital_usd=total,
            reserve_cash_usd=reserve,
            asset_weights=merged_asset_weights,
            sleeve_weights=merged_sleeve_weights,
            constraints=merged_constraints,
            metadata=merged_metadata,
        )
        try:
            request = self._approval_center.create_request(
                request_type="allocation_change",
                run_id=run_id,
                subject_id=str(preview_policy.get("policy_id") or f"allocation-{run_id}"),
                requested_by=agent_id,
                summary=f"Allocation policy change requested for run {run_id}.",
                payload={
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "total_capital_usd": total,
                    "reserve_cash_usd": reserve,
                    "asset_weights": merged_asset_weights,
                    "sleeve_weights": merged_sleeve_weights,
                    "constraints": merged_constraints,
                    "metadata": merged_metadata,
                    "preview_policy": preview_policy,
                },
            )
        except RuntimeError:
            return self._apply_allocation_policy(
                run_id=run_id,
                agent_id=agent_id,
                total_capital_usd=total,
                reserve_cash_usd=reserve,
                asset_weights=merged_asset_weights,
                sleeve_weights=merged_sleeve_weights,
                constraints=merged_constraints,
                metadata=merged_metadata,
            )
        self._log_event(
            "allocation.policy.approval_requested",
            run_id=run_id,
            agent_id=agent_id,
            payload={"request_id": request.get("request_id"), "asset_weights": merged_asset_weights},
        )
        return {"request": request, "preview_policy": preview_policy}

    def _apply_allocation_policy(
        self,
        *,
        run_id: str,
        agent_id: str,
        total_capital_usd: float | None = None,
        reserve_cash_usd: float | None = None,
        asset_weights: dict[str, Any] | None = None,
        sleeve_weights: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        latest = self.get_allocation_policy(run_id=run_id)
        total = float(total_capital_usd if total_capital_usd is not None else latest.get("total_capital_usd") or self._default_capital_usd)
        reserve = float(reserve_cash_usd if reserve_cash_usd is not None else latest.get("reserve_cash_usd") or self._default_reserve_cash_usd)
        merged_asset_weights = dict(latest.get("asset_weights") or {})
        merged_asset_weights.update(dict(asset_weights or {}))
        merged_sleeve_weights = dict(latest.get("sleeve_weights") or {})
        merged_sleeve_weights.update(dict(sleeve_weights or {}))
        merged_constraints = dict(latest.get("constraints") or {})
        merged_constraints.update(dict(constraints or {}))
        merged_metadata = dict(latest.get("metadata") or {})
        merged_metadata.update(dict(metadata or {}))
        policy_id = make_immutable_id("allocation-policy", run_id, agent_id, total, reserve, json.dumps(merged_asset_weights, sort_keys=True))
        policy = build_default_policy(
            run_id=run_id,
            total_capital_usd=total,
            reserve_cash_usd=reserve,
            asset_weights=merged_asset_weights,
            sleeve_weights=merged_sleeve_weights,
            constraints=merged_constraints,
            metadata=merged_metadata,
        )
        policy.update(
            {
                "policy_id": policy_id,
                "agent_id": agent_id,
                "created_at": latest.get("created_at") or datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        try:
            storage_db.save_allocation_policy(policy)
        except RuntimeError:
            pass
        self._log_event(
            "allocation.policy.updated",
            run_id=run_id,
            agent_id=agent_id,
            payload={
                "policy_id": policy_id,
                "asset_weights": policy.get("asset_weights"),
                "constraints": policy.get("constraints"),
            },
        )
        return self.allocation_policy_status(run_id=run_id)

    def get_allocation_policy(self, run_id: str | None = None) -> dict[str, Any]:
        try:
            stored = storage_db.load_latest_allocation_policy(run_id=run_id)
            if stored:
                return stored
        except RuntimeError:
            pass
        return build_default_policy(
            run_id=run_id,
            total_capital_usd=self._default_capital_usd,
            reserve_cash_usd=self._default_reserve_cash_usd,
            sleeve_weights=self._default_sleeve_weights,
        )

    def allocation_policy_status(self, run_id: str | None = None) -> dict[str, Any]:
        policy = self.get_allocation_policy(run_id=run_id)
        run_key = str(run_id or policy.get("run_id") or "").strip() or None
        positions = self._broker.list_positions(self._price_lookup)
        by_asset_class: dict[str, dict[str, Any]] = {}
        exposures: dict[str, float] = {}
        for position in positions:
            symbol = str(position.get("symbol") or "").upper().strip()
            asset_class = infer_asset_class(symbol, (position.get("metadata") or {}).get("asset_class") if isinstance(position.get("metadata"), dict) else None)
            market_value = float(position.get("market_value") or 0.0)
            if market_value <= 0:
                try:
                    market_value = float(position.get("qty") or 0.0) * float(position.get("market_price") or self._price_lookup(symbol))
                except Exception:
                    market_value = 0.0
            exposures[asset_class] = exposures.get(asset_class, 0.0) + max(0.0, market_value)
        with self._lock:
            used_notional = dict(self._run_asset_class_used_notional.get(run_key or "", {}))
        for asset_class, weight in dict(policy.get("asset_weights") or {}).items():
            allocated_usd = float(policy.get("deployable_capital_usd") or 0.0) * float(weight or 0.0)
            used_usd = max(exposures.get(asset_class, 0.0), used_notional.get(asset_class, 0.0))
            by_asset_class[asset_class] = {
                "weight": round(float(weight or 0.0), 4),
                "allocated_usd": round(allocated_usd, 2),
                "used_usd": round(used_usd, 2),
                "remaining_usd": round(max(0.0, allocated_usd - used_usd), 2),
                "live_exposure_usd": round(exposures.get(asset_class, 0.0), 2),
            }
        return {
            "policy": policy,
            "asset_classes": by_asset_class,
            "sleeves": self.sleeve_budget_status(run_id=run_key).get("runs", []),
        }

    def record_discovery_opportunity(self, opportunity: dict[str, Any]) -> dict[str, Any]:
        row = dict(opportunity or {})
        symbol = str(row.get("symbol") or "").upper().strip()
        if not symbol:
            raise ValueError("missing_symbol")
        run_id = str(row.get("run_id") or "").strip() or None
        asset_class = infer_asset_class(symbol, row.get("asset_class"))
        discovered_at = str(row.get("discovered_at") or datetime.utcnow().isoformat())
        opportunity_id = str(
            row.get("opportunity_id")
            or make_immutable_id("opportunity", run_id or "global", symbol, row.get("strategy_family") or "scanner", discovered_at[:16])
        )
        payload = {
            "opportunity_id": opportunity_id,
            "run_id": run_id,
            "symbol": symbol,
            "asset_class": asset_class,
            "strategy_family": row.get("strategy_family") or "scanner",
            "direction": row.get("direction") or "long_bias",
            "score": float(row.get("score") or 0.0),
            "confidence": float(row.get("confidence") or 0.0),
            "horizon": row.get("horizon") or "swing",
            "thesis": str(row.get("thesis") or f"Scanner candidate for {symbol}"),
            "catalysts": list(row.get("catalysts") or []),
            "evidence": list(row.get("evidence") or []),
            "ml": dict(row.get("ml") or {}),
            "metadata": dict(row.get("metadata") or {}),
            "status": str(row.get("status") or "candidate"),
            "discovered_at": discovered_at,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            storage_db.save_discovery_opportunity(payload)
        except RuntimeError:
            pass
        self._log_event(
            "scanner.opportunity.recorded",
            run_id=run_id,
            agent_id=str(row.get("agent_id") or "scanner"),
            payload={
                "opportunity_id": opportunity_id,
                "symbol": symbol,
                "asset_class": asset_class,
                "score": payload["score"],
                "confidence": payload["confidence"],
            },
        )
        return payload

    def list_discovery_opportunities(
        self,
        *,
        limit: int = 100,
        run_id: str | None = None,
        status: str | None = None,
        asset_class: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_asset_class = normalize_asset_class(asset_class) if asset_class else None
        try:
            return storage_db.load_discovery_opportunities(
                limit=limit,
                run_id=run_id,
                status=status,
                asset_class=normalized_asset_class,
            )
        except RuntimeError:
            return []

    def latest_discovery_opportunity(
        self,
        *,
        symbol: str,
        run_id: str | None = None,
    ) -> dict[str, Any] | None:
        normalized_symbol = str(symbol or "").upper().strip()
        if not normalized_symbol:
            return None
        rows = self.list_discovery_opportunities(limit=100, run_id=run_id)
        matches = [
            row for row in rows
            if str(row.get("symbol") or "").upper().strip() == normalized_symbol
        ]
        if not matches:
            return None
        matches.sort(
            key=lambda row: str(row.get("updated_at") or row.get("discovered_at") or ""),
            reverse=True,
        )
        return matches[0]

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
        allocation_state = self.allocation_policy_status(run_id=run_id)
        policy = allocation_state.get("policy") if isinstance(allocation_state.get("policy"), dict) else {}
        asset_class = infer_asset_class(
            normalized_symbol,
            (metadata or {}).get("asset_class") if isinstance(metadata, dict) else None,
        )
        asset_budget_state = (allocation_state.get("asset_classes") or {}).get(asset_class) or {}
        instrument_type = infer_instrument_type(normalized_symbol, asset_class)
        routing_mode = infer_routing_mode(normalized_symbol, asset_class)
        underlier_symbol = infer_underlier_symbol(normalized_symbol, asset_class)
        discovery_snapshot = self.latest_discovery_opportunity(run_id=run_id, symbol=normalized_symbol)
        discovery_ml = dict(discovery_snapshot.get("ml") or {}) if isinstance(discovery_snapshot, dict) else {}
        decision_scoring = {
            "symbol": normalized_symbol,
            "asset_class": asset_class,
            "strategy_family": discovery_snapshot.get("strategy_family") if isinstance(discovery_snapshot, dict) else None,
            "score": float(discovery_snapshot.get("score") or 0.0) if isinstance(discovery_snapshot, dict) else None,
            "confidence": float(discovery_snapshot.get("confidence") or 0.0) if isinstance(discovery_snapshot, dict) else None,
            "direction": discovery_snapshot.get("direction") if isinstance(discovery_snapshot, dict) else None,
            "horizon": discovery_snapshot.get("horizon") if isinstance(discovery_snapshot, dict) else None,
            "math_summary": discovery_ml.get("math_summary") if discovery_ml else None,
            "metrics": {
                "directional_probability_up": discovery_ml.get("directional_probability_up"),
                "technical_confidence": discovery_ml.get("technical_confidence"),
                "ml_confidence": discovery_ml.get("ml_confidence"),
                "sentiment_normalized": discovery_ml.get("sentiment_normalized"),
                "liquidity_score": discovery_ml.get("liquidity_score"),
                "volatility_score": discovery_ml.get("volatility_score"),
                "news_intensity_count": discovery_ml.get("news_intensity_count"),
                "regime_alignment": discovery_ml.get("regime_alignment"),
            },
        }
        positions = self._broker.list_positions(self._price_lookup)
        equity = self._current_equity(positions)
        intent_metadata = {
            "available_cash": self._broker.cash,
            "asset_class": asset_class,
            "instrument_type": instrument_type,
            "routing_mode": routing_mode,
            "underlier_symbol": underlier_symbol,
            "discovery_opportunity_id": discovery_snapshot.get("opportunity_id") if isinstance(discovery_snapshot, dict) else None,
            "strategy_family": decision_scoring.get("strategy_family"),
            "decision_scoring": decision_scoring,
            "ml_threshold_profile": decision_gate_thresholds,
            "allocation_policy_id": policy.get("policy_id"),
            "allocation_constraints": dict(policy.get("constraints") or {}),
            "asset_class_budget_allocated_usd": asset_budget_state.get("allocated_usd", 0.0),
            "asset_class_budget_used_usd": asset_budget_state.get("used_usd", 0.0),
            "asset_class_budget_remaining_usd": asset_budget_state.get("remaining_usd", 0.0),
            "sleeve_budget_allocated_usd": budget_state["allocated_usd"],
            "sleeve_budget_used_usd": budget_state["used_usd"],
            "sleeve_budget_remaining_usd": budget_state["remaining_usd"],
            "estimated_notional_usd": estimated_notional,
            **(metadata or {}),
        }
        portfolio_threshold_context = build_portfolio_threshold_context(
            symbol=normalized_symbol,
            asset_class=asset_class,
            positions=positions,
            equity=equity,
            notional=estimated_notional,
            metadata=intent_metadata,
        )
        decision_gate_thresholds = resolve_decision_gate_thresholds(
            self._settings,
            asset_class=asset_class,
            strategy_family=decision_scoring.get("strategy_family"),
            portfolio_context=portfolio_threshold_context,
        ).as_dict()
        decision_gate_thresholds["enabled"] = bool(self._settings.DECISION_GATE_ML_ENABLED)
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
            broker_mode=self._broker_mode,
            price=float(effective_price),
            asset_class=asset_class,
            instrument_type=instrument_type,
            routing_mode=routing_mode,
            underlier_symbol=underlier_symbol,
            metadata=intent_metadata,
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

        if self._require_trade_approval:
            try:
                approval_request = self._approval_center.create_request(
                    request_type="trade_execution",
                    run_id=run_id,
                    subject_id=decision_id,
                    requested_by=agent_id,
                    summary=f"Trade execution approval required for {normalized_symbol} {normalized_side} {float(quantity):g}.",
                    payload={
                        "run_id": run_id,
                        "agent_id": agent_id,
                        "decision_id": decision_id,
                        "risk_id": risk_id,
                        "intent_id": intent_id,
                        "trader_task_id": trader_task.task_id,
                        "intent": asdict(intent),
                        "effective_price": float(effective_price),
                        "estimated_notional_usd": estimated_notional,
                        "thesis_id": thesis_id,
                        "asset_class": asset_class,
                        "decision_scoring": decision_scoring,
                        "discovery_opportunity": discovery_snapshot,
                        "risk_gate": {
                            "policy_version": self._policy_version,
                            "asset_class_budget_allocated_usd": asset_budget_state.get("allocated_usd", 0.0),
                            "asset_class_budget_used_usd": asset_budget_state.get("used_usd", 0.0),
                            "asset_class_budget_remaining_usd": asset_budget_state.get("remaining_usd", 0.0),
                            "sleeve_budget_allocated_usd": budget_state["allocated_usd"],
                            "sleeve_budget_used_usd": budget_state["used_usd"],
                            "sleeve_budget_remaining_usd": budget_state["remaining_usd"],
                            "approved": approved,
                            "reasons": list(reasons),
                            "ml_thresholds": decision_gate_thresholds,
                        },
                        "metadata": dict(metadata or {}),
                    },
                )
            except RuntimeError:
                approval_request = None
            if approval_request is not None:
                self._task_bus.set_status(
                    trader_task.task_id,
                    "blocked",
                    {
                        "decision_id": decision_id,
                        "reason": "waiting_ceo_approval",
                        "approval_request_id": approval_request.get("request_id"),
                    },
                )
                self._decision_ledger.add_event(
                    event_type="approval.requested",
                    decision_id=decision_id,
                    order_id=None,
                    payload={
                        "request_id": approval_request.get("request_id"),
                        "request_type": "trade_execution",
                        "risk_id": risk_id,
                        "intent_id": intent_id,
                    },
                )
                self._log_event(
                    "decision.awaiting_ceo_approval",
                    run_id=run_id,
                    agent_id=agent_id,
                    decision_id=decision_id,
                    payload={
                        "request_id": approval_request.get("request_id"),
                        "asset_class": asset_class,
                        "estimated_notional_usd": estimated_notional,
                    },
                )
                return {
                    "status": "pending_approval",
                    "decision_id": decision_id,
                    "risk_id": risk_id,
                    "intent_id": intent_id,
                    "approval_request": approval_request,
                }

        self._decision_ledger.update_status(decision_id, "approved", {"risk_id": risk_id, "intent_id": intent_id})
        return self._execute_adapter_intent(
            intent=intent,
            trader_task_id=trader_task.task_id,
            estimated_notional_usd=estimated_notional,
        )

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

    def list_pending_approvals(self, *, limit: int = 100, request_type: str | None = None) -> list[dict[str, Any]]:
        return self._approval_center.list_requests(limit=limit, status="pending", request_type=request_type)

    def get_approval_request(self, request_id: str) -> dict[str, Any] | None:
        return self._approval_center.get_request(request_id)

    def find_pending_trade_approval(self, *, decision_id: str) -> dict[str, Any] | None:
        return self._approval_center.find_pending_by_subject(request_type="trade_execution", subject_id=decision_id)

    def find_pending_reroute_approval(self, *, signal_pack_id: str) -> dict[str, Any] | None:
        return self._approval_center.find_pending_by_subject(request_type="signal_pack_reroute", subject_id=signal_pack_id)

    def request_signal_pack_reroute(
        self,
        *,
        run_id: str,
        agent_id: str,
        signal_pack_id: str,
        assigned_roles: list[str],
        reason: str | None = None,
    ) -> dict[str, Any]:
        normalized_roles = [str(role).strip().lower() for role in assigned_roles if str(role).strip()]
        request = self._approval_center.create_request(
            request_type="signal_pack_reroute",
            run_id=run_id,
            subject_id=signal_pack_id,
            requested_by=agent_id,
            summary=f"Signal pack reroute requested for {signal_pack_id}.",
            payload={
                "run_id": run_id,
                "agent_id": agent_id,
                "signal_pack_id": signal_pack_id,
                "assigned_roles": normalized_roles,
                "reason": reason or "operator_reroute",
            },
        )
        self._log_event(
            "signal_pack.reroute.approval_requested",
            run_id=run_id,
            agent_id=agent_id,
            payload={"request_id": request.get("request_id"), "signal_pack_id": signal_pack_id, "assigned_roles": normalized_roles},
        )
        return {"request": request}

    def approve_request(self, request_id: str, *, reviewed_by: str, notes: str | None = None) -> dict[str, Any]:
        request = self._approval_center.get_request(request_id)
        if not request:
            raise ValueError("unknown_request_id")
        if request.get("status") != "pending":
            return {"status": request.get("status"), "request": request}
        request_type = str(request.get("request_type") or "").strip().lower()
        payload = dict(request.get("payload") or {})
        if request_type == "trade_execution":
            result = self._execute_approved_trade_request(request)
            resolved = self._approval_center.resolve_request(
                request_id,
                resolution="approved",
                reviewed_by=reviewed_by,
                notes=notes,
                resolution_payload={"execution_result": result},
            )
            return {"status": "approved", "request": resolved, "result": result}
        if request_type == "allocation_change":
            result = self._apply_allocation_policy(
                run_id=str(payload.get("run_id") or ""),
                agent_id=str(payload.get("agent_id") or reviewed_by),
                total_capital_usd=payload.get("total_capital_usd"),
                reserve_cash_usd=payload.get("reserve_cash_usd"),
                asset_weights=payload.get("asset_weights") if isinstance(payload.get("asset_weights"), dict) else None,
                sleeve_weights=payload.get("sleeve_weights") if isinstance(payload.get("sleeve_weights"), dict) else None,
                constraints=payload.get("constraints") if isinstance(payload.get("constraints"), dict) else None,
                metadata={**dict(payload.get("metadata") or {}), "approved_by": reviewed_by},
            )
            resolved = self._approval_center.resolve_request(
                request_id,
                resolution="approved",
                reviewed_by=reviewed_by,
                notes=notes,
                resolution_payload={"allocation_result": result},
            )
            return {"status": "approved", "request": resolved, "result": result}
        if request_type == "signal_pack_reroute":
            result = self._apply_signal_pack_reroute_request(request)
            resolved = self._approval_center.resolve_request(
                request_id,
                resolution="approved",
                reviewed_by=reviewed_by,
                notes=notes,
                resolution_payload={"reroute_result": result},
            )
            return {"status": "approved", "request": resolved, "result": result}
        resolved = self._approval_center.resolve_request(request_id, resolution="approved", reviewed_by=reviewed_by, notes=notes)
        return {"status": "approved", "request": resolved}

    def reject_request(self, request_id: str, *, reviewed_by: str, notes: str | None = None) -> dict[str, Any]:
        request = self._approval_center.get_request(request_id)
        if not request:
            raise ValueError("unknown_request_id")
        request_type = str(request.get("request_type") or "").strip().lower()
        subject_id = str(request.get("subject_id") or "").strip()
        if request_type == "trade_execution" and subject_id:
            self._decision_ledger.update_status(subject_id, "blocked", {"reason": "ceo_rejected", "reviewed_by": reviewed_by})
        resolved = self._approval_center.resolve_request(request_id, resolution="rejected", reviewed_by=reviewed_by, notes=notes)
        return {"status": "rejected", "request": resolved}

    def _execute_adapter_intent(
        self,
        *,
        intent: AdapterExecutionIntent,
        trader_task_id: str | None = None,
        estimated_notional_usd: float | None = None,
    ) -> dict[str, Any]:
        execution_result = self._execution_adapter.execute(intent)
        order_id = (execution_result.get("order") or {}).get("id")
        execution_status = execution_result.get("status")
        estimated_notional = float(
            estimated_notional_usd
            if estimated_notional_usd is not None
            else float(intent.quantity) * float(intent.price or 0.0)
        )
        sleeve = Sleeve(str(intent.sleeve or "tactical"))
        if execution_status == "executed":
            self._update_run_sleeve_used_notional(
                run_id=intent.run_id,
                sleeve=sleeve,
                side=intent.side,
                quantity=float((execution_result.get("order") or {}).get("quantity") or intent.quantity),
                price=float((execution_result.get("order") or {}).get("avg_price") or intent.price or 0.0),
            )
            with self._lock:
                asset_used = self._run_asset_class_used_notional.setdefault(intent.run_id, {})
                delta = estimated_notional if intent.side == "buy" else -estimated_notional
                asset_used[intent.asset_class] = max(0.0, float(asset_used.get(intent.asset_class, 0.0)) + delta)

        if trader_task_id:
            if execution_status == "executed":
                self._task_bus.set_status(trader_task_id, "completed", {"order_id": order_id})
            else:
                self._task_bus.set_status(
                    trader_task_id,
                    "blocked",
                    {"decision_id": intent.decision_id, "reason": execution_result.get("reason")},
                )

        decision_status = "executed" if execution_status == "executed" else "blocked"
        self._decision_ledger.update_status(
            intent.decision_id,
            decision_status,
            {"order_id": order_id, "execution_status": execution_status},
        )
        self._decision_ledger.add_event(
            event_type="execution.processed",
            decision_id=intent.decision_id,
            order_id=order_id,
            payload=execution_result,
        )
        self._audit_log.record(
            "execution.intent.processed",
            {
                "run_id": intent.run_id,
                "decision_id": intent.decision_id,
                "risk_id": intent.risk_id,
                "intent_id": intent.intent_id,
                "order_id": order_id,
                "status": execution_status,
                "reason": execution_result.get("reason"),
            },
        )
        self._log_event(
            "decision.executed" if execution_status == "executed" else "decision.execution_rejected",
            run_id=intent.run_id,
            agent_id=intent.agent_id,
            decision_id=intent.decision_id,
            payload={
                "order_id": order_id,
                "execution_status": execution_status,
                "asset_class": intent.asset_class,
                "sleeve_budget": self._ensure_run_sleeve_budget(run_id=intent.run_id, sleeve=sleeve),
            },
        )
        return {
            "status": execution_status,
            "decision_id": intent.decision_id,
            "risk_id": intent.risk_id,
            "intent_id": intent.intent_id,
            "order_id": order_id,
            "execution": execution_result,
        }

    def _execute_approved_trade_request(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = dict(request.get("payload") or {})
        raw_intent = payload.get("intent") if isinstance(payload.get("intent"), dict) else {}
        if not raw_intent:
            raise ValueError("missing_trade_intent")
        intent = AdapterExecutionIntent(**raw_intent)
        self._decision_ledger.update_status(
            intent.decision_id,
            "approved",
            {
                "risk_id": intent.risk_id,
                "intent_id": intent.intent_id,
                "approved_via_request_id": request.get("request_id"),
            },
        )
        self._decision_ledger.add_event(
            event_type="approval.approved",
            decision_id=intent.decision_id,
            order_id=None,
            payload={"request_id": request.get("request_id"), "request_type": "trade_execution"},
        )
        return self._execute_adapter_intent(
            intent=intent,
            trader_task_id=str(payload.get("trader_task_id") or "").strip() or None,
            estimated_notional_usd=float(payload.get("estimated_notional_usd") or 0.0),
        )

    def _apply_signal_pack_reroute_request(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = dict(request.get("payload") or {})
        signal_pack_id = str(payload.get("signal_pack_id") or request.get("subject_id") or "").strip()
        assigned_roles = payload.get("assigned_roles") if isinstance(payload.get("assigned_roles"), list) else []
        if not signal_pack_id:
            raise ValueError("missing_signal_pack_id")
        if not assigned_roles:
            raise ValueError("missing_assigned_roles")
        from app.fund.agent_runtime import fund_agent_runtime

        return fund_agent_runtime.reroute_signal_pack(
            signal_pack_id=signal_pack_id,
            assigned_roles=assigned_roles,
            reason=str(payload.get("reason") or "approved_reroute"),
        )

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
            self._run_asset_class_used_notional.setdefault(run_id, {})

    def _ensure_run_budget_initialized(self, run_id: str) -> None:
        with self._lock:
            if run_id in self._run_sleeve_allocations:
                return
        policy = self.get_allocation_policy(run_id=run_id)
        total_capital_usd = float(policy.get("total_capital_usd") or self._default_capital_usd)
        reserve_cash_usd = float(policy.get("reserve_cash_usd") or self._default_reserve_cash_usd)
        target_weights = dict(policy.get("sleeve_weights") or self._default_sleeve_weights)
        allocation = self.allocate_sleeves(
            run_id=run_id,
            total_capital_usd=total_capital_usd,
            reserve_cash_usd=reserve_cash_usd,
            decision_id=make_immutable_id("budget", run_id),
            target_weights=target_weights,
        )
        self._log_event(
            "sleeve_budget.initialized",
            run_id=run_id,
            payload={"allocation_id": allocation.get("allocation_id"), "weights": target_weights},
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
