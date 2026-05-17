from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .service import data_pipeline

router = APIRouter(prefix="/data-pipeline", tags=["data-pipeline"])


class PipelineRunIn(BaseModel):
    symbols: list[str] | None = Field(default=None)


@router.get("/status")
async def pipeline_status():
    return data_pipeline.status()


@router.post("/run")
async def run_pipeline(body: PipelineRunIn):
    try:
        symbols = body.symbols if body.symbols else None
        return data_pipeline.run_cycle(symbols=symbols, run_type="manual_api")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/features/{symbol}")
async def latest_features(symbol: str):
    return {
        "symbol": symbol.upper(),
        "items": data_pipeline.latest_features(symbol.upper()),
    }


@router.get("/storage-estimate")
async def storage_estimate(symbols: int | None = None):
    return data_pipeline.storage_estimate(symbols=symbols)


@router.get("/warehouse/{table}")
async def warehouse_rows(table: str, limit: int = 50):
    try:
        return {"table": table, "items": data_pipeline.latest_rows(table, limit=max(1, min(limit, 500)))}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/snapshots/{snapshot_id}")
async def replay_snapshot(snapshot_id: str):
    snapshot = data_pipeline.replay_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    return snapshot
