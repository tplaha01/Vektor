from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.fund.contracts import (
    ProvenanceRef,
    ResearchReport as ContractResearchReport,
    SentimentSnapshot as ContractSentimentSnapshot,
    Sleeve,
)
from app.fund.agent_runtime import FundAgentRuntime, fund_agent_runtime
from app.fund.openclaw_command_adapter import OpenClawCommandAdapter, openclaw_command_adapter
from app.fund.orchestrator import FirmOrchestrator, firm_orchestrator
from app.fund.performance_tracker import performance_tracker
from app.fund.realtime_stream import realtime_stream
from app.fund.runtime_guard import data_integrity_guard

router = APIRouter(prefix="/fund", tags=["fund"])


def get_orchestrator() -> FirmOrchestrator:
    return firm_orchestrator


def get_agent_runtime() -> FundAgentRuntime:
    return fund_agent_runtime


def get_openclaw_command_adapter() -> OpenClawCommandAdapter:
    return openclaw_command_adapter


class SleeveAllocationIn(BaseModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    total_capital_usd: float = Field(..., gt=0)
    reserve_cash_usd: float = Field(default=0, ge=0)
    decision_id: str | None = Field(default=None, min_length=3, max_length=128)
    target_weights: dict[str, float] | None = None


class AllocationPolicyIn(BaseModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(default="ceo", min_length=2, max_length=128)
    total_capital_usd: float | None = Field(default=None, gt=0)
    reserve_cash_usd: float | None = Field(default=None, ge=0)
    asset_weights: dict[str, float] = Field(default_factory=dict)
    sleeve_weights: dict[str, float] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchProvenanceIn(BaseModel):
    source_type: Literal["data", "research", "thesis", "risk", "execution", "allocation", "sentiment"]
    source_id: str = Field(..., min_length=3, max_length=128)


class ResearchReportIn(BaseModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    asset_universe: list[str] = Field(default_factory=list)
    summary: str = Field(..., min_length=1, max_length=6000)
    findings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance: list[ResearchProvenanceIn] = Field(default_factory=list)


class ThesisCreateIn(BaseModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    sleeve: Sleeve
    report_ids: list[str] = Field(..., min_length=1)
    statement: str = Field(..., min_length=1, max_length=4000)
    conviction: float = Field(default=0.0, ge=0.0, le=1.0)


class DecisionExecuteIn(BaseModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    thesis_id: str = Field(..., min_length=3, max_length=128)
    symbol: str = Field(..., min_length=1, max_length=32)
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)
    price: float | None = Field(default=None, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SentimentIn(BaseModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    symbol: str = Field(..., min_length=1, max_length=32)
    source: str = Field(..., min_length=2, max_length=128)
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance_url: str | None = Field(default=None, max_length=1024)


class OpenClawIngestIn(BaseModel):
    kind: str = Field(..., min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class CeoCommandIn(BaseModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    command: str = Field(..., min_length=1, max_length=4000)
    agent_id: str = Field(default="ceo", min_length=2, max_length=128)
    target_role: Literal[
        "technical_analyst",
        "fundamental_analyst",
        "sentiment_analyst",
        "ml_timeseries_analyst",
        "insight_researcher",
        "hedge_fund_researcher",
        "fund_manager",
        "trader",
        "risk_auditor",
        "blog_writer",
    ] | None = None
    orchestrate_swarm: bool = False
    symbol: str | None = Field(default=None, min_length=1, max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=8, ge=0, le=10)


class OpenClawCommandIn(BaseModel):
    platform: str = Field(default="discord", min_length=2, max_length=64)
    channel_id: str | None = Field(default=None, max_length=256)
    channel_name: str | None = Field(default=None, max_length=256)
    sender_id: str | None = Field(default=None, max_length=256)
    sender_name: str | None = Field(default=None, max_length=256)
    message_id: str | None = Field(default=None, max_length=256)
    text: str = Field(..., min_length=1, max_length=4000)
    run_id: str | None = Field(default=None, min_length=3, max_length=128)
    agent_id: str | None = Field(default=None, min_length=2, max_length=128)
    target_role: Literal[
        "technical_analyst",
        "fundamental_analyst",
        "sentiment_analyst",
        "ml_timeseries_analyst",
        "insight_researcher",
        "hedge_fund_researcher",
        "fund_manager",
        "trader",
        "risk_auditor",
        "signal_swarm",
        "blog_writer",
    ] | None = None
    priority: int = Field(default=8, ge=0, le=10)
    payload: dict[str, Any] = Field(default_factory=dict)


class AutopilotKickIn(BaseModel):
    run_id: str | None = Field(default=None, min_length=3, max_length=128)


class KnowledgeResetIn(BaseModel):
    run_id: str | None = Field(default=None, min_length=3, max_length=128)
    agent_id: str = Field(default="ceo", min_length=2, max_length=128)
    seed_event: bool = True


class DevelopmentLogIn(BaseModel):
    entry_id: str = Field(..., min_length=3, max_length=128)
    stage: Literal["start", "update", "end"]
    actor_name: str = Field(..., min_length=2, max_length=128)
    actor_platform: Literal["codex", "claude_code", "github_copilot", "ollama", "other"]
    actor_model: str = Field(..., min_length=2, max_length=128)
    actor_provider: str | None = Field(default=None, max_length=128)
    run_id: str | None = Field(default=None, min_length=3, max_length=128)
    branch: str | None = Field(default=None, max_length=128)
    commit_start: str | None = Field(default=None, max_length=128)
    commit_end: str | None = Field(default=None, max_length=128)
    scope: str = Field(default="", max_length=4000)
    files: list[str] = Field(default_factory=list)
    validation: str = Field(default="", max_length=4000)
    notes: str = Field(default="", max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PerformanceCaptureIn(BaseModel):
    snapshot_kind: Literal["manual", "intraday", "daily", "startup"] = "manual"
    reason: str = Field(default="manual", min_length=1, max_length=256)


@router.post("/allocator/allocate")
async def allocate_sleeves_endpoint(
    body: SleeveAllocationIn,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.allocate_sleeves(
        run_id=body.run_id,
        total_capital_usd=body.total_capital_usd,
        reserve_cash_usd=body.reserve_cash_usd,
        decision_id=body.decision_id,
        target_weights=body.target_weights,
    )


@router.post("/allocation/policy")
async def set_allocation_policy_endpoint(
    body: AllocationPolicyIn,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.set_allocation_policy(
        run_id=body.run_id,
        agent_id=body.agent_id,
        total_capital_usd=body.total_capital_usd,
        reserve_cash_usd=body.reserve_cash_usd,
        asset_weights=body.asset_weights,
        sleeve_weights=body.sleeve_weights,
        constraints=body.constraints,
        metadata=body.metadata,
    )


@router.get("/allocation/policy")
async def get_allocation_policy_endpoint(
    run_id: str | None = Query(default=None, min_length=3, max_length=128),
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.allocation_policy_status(run_id=run_id)


@router.get("/discovery/opportunities")
async def discovery_opportunities(
    limit: int = Query(default=100, ge=1, le=2000),
    run_id: str | None = Query(default=None, min_length=3, max_length=128),
    status: str | None = Query(default=None, min_length=2, max_length=64),
    asset_class: str | None = Query(default=None, min_length=2, max_length=64),
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return {
        "opportunities": orchestrator.list_discovery_opportunities(
            limit=limit,
            run_id=run_id,
            status=status,
            asset_class=asset_class,
        )
    }


@router.post("/research/reports")
async def create_research_report(
    body: ResearchReportIn,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    report = ContractResearchReport(
        run_id=body.run_id,
        agent_id=body.agent_id,
        asset_universe=tuple(body.asset_universe),
        summary=body.summary,
        findings=tuple(body.findings) if body.findings else (body.summary,),
        confidence=Decimal(str(body.confidence)),
        provenance=tuple(
            ProvenanceRef(source_type=item.source_type, source_id=item.source_id)
            for item in body.provenance
        ),
    )
    return orchestrator.submit_research(report)


@router.post("/theses")
async def create_thesis(
    body: ThesisCreateIn,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    try:
        return orchestrator.create_thesis(
            run_id=body.run_id,
            agent_id=body.agent_id,
            sleeve=body.sleeve,
            report_ids=body.report_ids,
            statement=body.statement,
            conviction=Decimal(str(body.conviction)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/decisions/execute")
async def execute_decision(
    body: DecisionExecuteIn,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    try:
        return orchestrator.execute_decision(
            run_id=body.run_id,
            agent_id=body.agent_id,
            thesis_id=body.thesis_id,
            symbol=body.symbol,
            side=body.side,
            quantity=body.quantity,
            price=body.price,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sentiment/ingest")
async def ingest_sentiment(
    body: SentimentIn,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    snapshot = ContractSentimentSnapshot(
        run_id=body.run_id,
        agent_id=body.agent_id,
        symbol=body.symbol,
        source=body.source,
        sentiment_score=body.sentiment_score,
        confidence=body.confidence,
        provenance_url=body.provenance_url,
    )
    return orchestrator.submit_sentiment(snapshot)


@router.get("/agents/tasks/active")
async def active_tasks(orchestrator: FirmOrchestrator = Depends(get_orchestrator)):
    return orchestrator.list_active_tasks()


@router.get("/agents/tasks/history")
async def task_history(
    limit: int = Query(default=200, ge=1, le=5000),
    run_id: str | None = Query(default=None, min_length=3, max_length=128),
    agent_id: str | None = Query(default=None, min_length=2, max_length=128),
    role: str | None = Query(default=None, min_length=2, max_length=128),
    status: Literal["queued", "running", "completed", "failed", "blocked"] | None = None,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.list_task_history(
        limit=limit,
        run_id=run_id,
        agent_id=agent_id,
        role=role,
        status=status,
    )


@router.get("/agents/workers/status")
async def worker_status(runtime: FundAgentRuntime = Depends(get_agent_runtime)):
    return runtime.status()


@router.get("/agents/autopilot/status")
async def autopilot_status(runtime: FundAgentRuntime = Depends(get_agent_runtime)):
    status = runtime.status()
    return {
        "runtime_started": status.get("started", False),
        "autopilot": status.get("autopilot", {}),
    }


@router.post("/agents/autopilot/kick")
async def autopilot_kick(
    body: AutopilotKickIn,
    background_tasks: BackgroundTasks,
    runtime: FundAgentRuntime = Depends(get_agent_runtime),
):
    if not runtime.is_started():
        result = {"accepted": False, "reason": "runtime_not_started"}
    elif data_integrity_guard.halted():
        result = {"accepted": False, "reason": data_integrity_guard.halt_reason() or "system_halted"}
    else:
        run_id = str(body.run_id or f"run-autopilot-{uuid4().hex[:12]}")
        background_tasks.add_task(runtime.kick_autopilot, run_id)
        result = {
            "accepted": True,
            "manual": True,
            "queued": True,
            "run_id": run_id,
            "message": "Autopilot cycle scheduled in background.",
        }
    if not result.get("accepted"):
        raise HTTPException(status_code=400, detail=result.get("reason", "autopilot_rejected"))
    return result


@router.post("/ceo/commands")
async def ceo_commands(
    body: CeoCommandIn,
    runtime: FundAgentRuntime = Depends(get_agent_runtime),
):
    if body.orchestrate_swarm:
        return runtime.enqueue_signal_swarm(
            run_id=body.run_id,
            symbol=str(body.symbol or body.payload.get("symbol") or "SPY").upper().strip(),
            agent_id=body.agent_id,
            command=body.command,
            payload=body.payload,
            priority=body.priority,
        )
    return runtime.enqueue_ceo_command(
        run_id=body.run_id,
        command=body.command,
        agent_id=body.agent_id,
        target_role=body.target_role,
        payload=body.payload,
        priority=body.priority,
    )


@router.get("/decisions/pending")
async def pending_decisions(orchestrator: FirmOrchestrator = Depends(get_orchestrator)):
    return orchestrator.list_pending_decisions()


@router.get("/sleeves/budgets")
async def sleeve_budgets(
    run_id: str | None = Query(default=None, min_length=3, max_length=128),
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.sleeve_budget_status(run_id=run_id)


@router.get("/trades/blocked")
async def blocked_trades(
    limit: int = Query(default=100, ge=1, le=1000),
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.list_blocked_trades(limit=limit)


@router.get("/audit/orders/{order_id}/timeline")
async def audit_timeline(order_id: str, orchestrator: FirmOrchestrator = Depends(get_orchestrator)):
    return orchestrator.audit_timeline_for_order(order_id)


@router.post("/openclaw/ingest")
async def openclaw_ingest(
    body: OpenClawIngestIn,
    x_openclaw_token: str | None = Header(default=None, alias="X-OpenClaw-Token"),
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    if not x_openclaw_token:
        raise HTTPException(status_code=401, detail="missing_openclaw_token")
    result = orchestrator.ingest_openclaw(kind=body.kind, payload=body.payload, token=x_openclaw_token)
    if not result.get("accepted") and result.get("reason") == "unauthorized":
        raise HTTPException(status_code=401, detail="invalid_openclaw_token")
    return result


@router.get("/openclaw/health")
async def openclaw_health(orchestrator: FirmOrchestrator = Depends(get_orchestrator)):
    return orchestrator.openclaw_health()


@router.post("/openclaw/commands")
async def openclaw_commands(
    body: OpenClawCommandIn,
    x_openclaw_token: str | None = Header(default=None, alias="X-OpenClaw-Token"),
    adapter: OpenClawCommandAdapter = Depends(get_openclaw_command_adapter),
):
    if not x_openclaw_token:
        raise HTTPException(status_code=401, detail="missing_openclaw_token")
    result = adapter.route_message(body.model_dump(mode="json"), token=x_openclaw_token)
    if result.get("accepted"):
        return result
    reason = result.get("reason")
    if reason == "unauthorized":
        raise HTTPException(status_code=401, detail="invalid_openclaw_token")
    raise HTTPException(status_code=400, detail=reason or "openclaw_command_rejected")


@router.get("/openclaw/commands/health")
async def openclaw_commands_health(adapter: OpenClawCommandAdapter = Depends(get_openclaw_command_adapter)):
    return adapter.health()


@router.get("/openclaw/commands/rejections")
async def openclaw_commands_rejections(
    limit: int = Query(default=100, ge=1, le=1000),
    adapter: OpenClawCommandAdapter = Depends(get_openclaw_command_adapter),
):
    return adapter.list_rejected(limit=limit)


@router.get("/openclaw/commands/accepted")
async def openclaw_commands_accepted(
    limit: int = Query(default=100, ge=1, le=1000),
    adapter: OpenClawCommandAdapter = Depends(get_openclaw_command_adapter),
):
    return adapter.list_accepted(limit=limit)


@router.get("/openclaw/rejections")
async def openclaw_rejections(
    limit: int = Query(default=100, ge=1, le=1000),
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.openclaw_rejections(limit=limit)


@router.get("/knowledge/events")
async def knowledge_events(
    limit: int = Query(default=200, ge=1, le=2000),
    namespace: str | None = None,
    source: str | None = None,
    event_type: str | None = None,
    run_id: str | None = None,
    agent_id: str | None = None,
    decision_id: str | None = None,
    order_id: str | None = None,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.list_knowledge_events(
        limit=limit,
        namespace=namespace,
        source=source,
        event_type=event_type,
        run_id=run_id,
        agent_id=agent_id,
        decision_id=decision_id,
        order_id=order_id,
    )


@router.get("/knowledge/lineage")
async def knowledge_lineage(
    limit: int = Query(default=500, ge=1, le=5000),
    run_id: str | None = None,
    decision_id: str | None = None,
    order_id: str | None = None,
    report_id: str | None = None,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    if not any([run_id, decision_id, order_id, report_id]):
        raise HTTPException(status_code=400, detail="provide_at_least_one_filter")
    return orchestrator.knowledge_lineage(
        run_id=run_id,
        decision_id=decision_id,
        order_id=order_id,
        report_id=report_id,
        limit=limit,
    )


@router.get("/knowledge/stats")
async def knowledge_stats(orchestrator: FirmOrchestrator = Depends(get_orchestrator)):
    return orchestrator.knowledge_stats()


@router.post("/knowledge/development/log")
async def knowledge_development_log(
    body: DevelopmentLogIn,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.ingest_development_log(
        entry_id=body.entry_id,
        stage=body.stage,
        actor_name=body.actor_name,
        actor_platform=body.actor_platform,
        actor_model=body.actor_model,
        actor_provider=body.actor_provider,
        run_id=body.run_id,
        branch=body.branch,
        commit_start=body.commit_start,
        commit_end=body.commit_end,
        scope=body.scope,
        files=body.files,
        validation=body.validation,
        notes=body.notes,
        metadata=body.metadata,
    )


@router.post("/knowledge/reset")
async def knowledge_reset(
    body: KnowledgeResetIn,
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.reset_knowledge_graph(
        run_id=body.run_id,
        agent_id=body.agent_id,
        seed_event=body.seed_event,
    )


@router.post("/performance/capture")
async def performance_capture(body: PerformanceCaptureIn):
    return await performance_tracker.capture_snapshot(
        snapshot_kind=body.snapshot_kind,
        reason=body.reason,
    )


@router.get("/performance/snapshots")
async def performance_snapshots(
    limit: int = Query(default=500, ge=1, le=5000),
    snapshot_kind: Literal["manual", "intraday", "daily", "startup"] | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
):
    return performance_tracker.list_snapshots(
        limit=limit,
        snapshot_kind=snapshot_kind,
        start_at=start_at,
        end_at=end_at,
    )


@router.get("/performance/summary")
async def performance_summary():
    return performance_tracker.summary()


@router.post("/performance/reset")
async def performance_reset():
    return performance_tracker.reset()


@router.get("/stream/status")
async def stream_status():
    return realtime_stream.stats()


@router.websocket("/stream")
async def stream_events(
    websocket: WebSocket,
    cursor: str | None = None,
):
    await websocket.accept()
    current_cursor = cursor
    await websocket.send_json(
        {
            "type": "fund.stream.ready",
            "cursor": realtime_stream.latest_cursor(),
            "stream": realtime_stream.stats(),
        }
    )

    idle_ticks = 0
    poll_interval = 0.5
    heartbeat_ticks = 30  # 15 seconds

    try:
        while True:
            events = realtime_stream.after(cursor=current_cursor, limit=250)
            if events:
                for event in events:
                    await websocket.send_json({"type": "fund.event", "data": event})
                current_cursor = str(events[-1].get("stream_id"))
                idle_ticks = 0
            else:
                idle_ticks += 1
                if idle_ticks >= heartbeat_ticks:
                    await websocket.send_json(
                        {
                            "type": "fund.stream.heartbeat",
                            "cursor": current_cursor,
                            "event_count": realtime_stream.stats().get("event_count", 0),
                        }
                    )
                    idle_ticks = 0
            await asyncio.sleep(poll_interval)
    except WebSocketDisconnect:
        return
