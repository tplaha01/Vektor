"""
Knowledge graph query and ingestion routes for developer/operator access.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.fund.orchestrator import FirmOrchestrator, firm_orchestrator


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def get_orchestrator() -> FirmOrchestrator:
    return firm_orchestrator


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


@router.get("/stats")
async def get_knowledge_stats(orchestrator: FirmOrchestrator = Depends(get_orchestrator)):
    return orchestrator.knowledge_stats()


@router.get("/events")
async def get_knowledge_events(
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


@router.get("/lineage")
async def get_knowledge_lineage(
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


@router.post("/development/log")
async def ingest_development_log(
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
