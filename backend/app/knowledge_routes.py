"""
Development Knowledge Graph Routes
Handles devlog ingestion and querying per DevViktor specification
"""
from typing import Any, Dict, List
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.fund.knowledge_graph import knowledge_graph

router = APIRouter(prefix="/fund/knowledge", tags=["knowledge"])


class DevLogPayload(BaseModel):
    """Payload for dev session logging"""
    entry_id: str
    stage: str  # start, update, end
    actor_name: str
    actor_platform: str
    actor_model: str
    actor_provider: str
    run_id: str
    branch: str
    commit_start: str = ""
    commit_end: str = ""
    scope: str
    files: List[str] = []
    validation: str
    notes: str


@router.post("/development/log")
async def ingest_dev_log(payload: DevLogPayload) -> Dict[str, Any]:
    """
    Ingest development session log entry into knowledge graph
    
    Per DevViktor.md: Every START and END entry must be written here.
    Creates a namespaced development.devlog.* event in the KB.
    """
    try:
        event_data = payload.dict()
        event_id = knowledge_graph.capture(
            namespace="development",
            entity_type=f"devlog_{payload.stage}",
            data=event_data,
        )
        
        return {
            "status": "ingested",
            "entry_id": payload.entry_id,
            "event_id": event_id,
            "stage": payload.stage,
            "run_id": payload.run_id,
        }
    except Exception as e:
        return {
            "status": "error",
            "entry_id": payload.entry_id,
            "error": str(e),
        }


@router.get("/stats")
async def get_knowledge_stats() -> Dict[str, Any]:
    """Get overall knowledge graph statistics"""
    from app.fund.orchestrator import firm_orchestrator
    
    stats = firm_orchestrator.knowledge_stats()
    return {
        "event_count": stats.get("event_count", 0),
        "entity_count": stats.get("entity_count", 0),
        "namespaces": stats.get("namespaces", []),
    }


@router.get("/events")
async def get_knowledge_events(
    namespace: str = Query("development", description="Event namespace"),
    limit: int = Query(50, ge=1, le=1000),
) -> Dict[str, Any]:
    """Query knowledge graph events by namespace"""
    try:
        # This would query from the actual KG storage
        # For now, return metadata about available queries
        return {
            "namespace": namespace,
            "limit": limit,
            "status": "query_capability_available",
            "note": "Implement event querying from knowledge_graph storage",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("/development/logs")
async def get_dev_logs(
    run_id: str = Query(None, description="Filter by run_id"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Query development session logs"""
    return {
        "run_id": run_id,
        "limit": limit,
        "logs": [],
        "status": "querying from knowledge graph",
    }
