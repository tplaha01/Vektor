from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.fund.contracts import (
    ProvenanceRef,
    ResearchReport as ContractResearchReport,
    SentimentSnapshot as ContractSentimentSnapshot,
    Sleeve,
)
from app.fund.orchestrator import FirmOrchestrator, firm_orchestrator

router = APIRouter(prefix="/fund", tags=["fund"])


def get_orchestrator() -> FirmOrchestrator:
    return firm_orchestrator


class SleeveAllocationIn(BaseModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    total_capital_usd: float = Field(..., gt=0)
    reserve_cash_usd: float = Field(default=0, ge=0)
    decision_id: str | None = Field(default=None, min_length=3, max_length=128)
    target_weights: dict[str, float] | None = None


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


@router.get("/decisions/pending")
async def pending_decisions(orchestrator: FirmOrchestrator = Depends(get_orchestrator)):
    return orchestrator.list_pending_decisions()


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


@router.get("/openclaw/rejections")
async def openclaw_rejections(
    limit: int = Query(default=100, ge=1, le=1000),
    orchestrator: FirmOrchestrator = Depends(get_orchestrator),
):
    return orchestrator.openclaw_rejections(limit=limit)
