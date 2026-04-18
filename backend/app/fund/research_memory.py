from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ResearchProvenance(BaseModel):
    source: str = Field(..., description="Originating system, feed, or analyst.")
    timestamp: datetime = Field(default_factory=_utc_now)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_url: Optional[str] = None
    external_id: Optional[str] = None

    @field_validator("source")
    @classmethod
    def _source_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source cannot be empty")
        return value

    @field_validator("timestamp")
    @classmethod
    def _normalize_timestamp(cls, value: datetime) -> datetime:
        return _to_utc(value)


class ResearchReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    created_at: datetime = Field(default_factory=_utc_now)
    assets: List[str] = Field(default_factory=list)
    title: str
    summary: str
    thesis: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance: List[ResearchProvenance] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)

    @field_validator("agent_id", "title", "summary")
    @classmethod
    def _required_text_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be empty")
        return value

    @field_validator("created_at")
    @classmethod
    def _normalize_created_at(cls, value: datetime) -> datetime:
        return _to_utc(value)

    @field_validator("assets")
    @classmethod
    def _normalize_assets(cls, value: List[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for item in value:
            symbol = item.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            normalized.append(symbol)
        return normalized

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: List[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for item in value:
            tag = item.strip().lower()
            if not tag or tag in seen:
                continue
            seen.add(tag)
            normalized.append(tag)
        return normalized


class ResearchMemoryStore:
    """
    In-memory, schema-backed store for research reports.

    Provides:
    - write path via `add_report`/`add_many`
    - immutable-id keyed retrieval
    - helper retrieval by asset
    - helper retrieval by recent window
    """

    def __init__(
        self,
        max_reports: int = 5000,
        event_sink: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.max_reports = max_reports
        self._lock = RLock()
        self._reports: Dict[str, ResearchReport] = {}
        self._ordered_ids: List[str] = []
        self._asset_index: Dict[str, List[str]] = defaultdict(list)
        self._event_sink = event_sink

    def add_report(self, report: ResearchReport) -> ResearchReport:
        model = report if isinstance(report, ResearchReport) else ResearchReport.model_validate(report)
        with self._lock:
            existing = self._reports.get(model.report_id)
            if existing is None:
                self._ordered_ids.append(model.report_id)
            else:
                for symbol in existing.assets:
                    ids = self._asset_index.get(symbol)
                    if ids:
                        self._asset_index[symbol] = [rid for rid in ids if rid != existing.report_id]

            self._reports[model.report_id] = model
            for symbol in model.assets:
                self._asset_index[symbol].append(model.report_id)

            self._prune_if_needed()
            self._emit_event(model)
        return model

    def add_many(self, reports: Iterable[ResearchReport | dict]) -> List[ResearchReport]:
        saved: List[ResearchReport] = []
        for report in reports:
            saved.append(self.add_report(report))
        return saved

    def get_report(self, id: str) -> Optional[ResearchReport]:
        with self._lock:
            return self._reports.get(id)

    def list_recent(self, limit: int = 100) -> List[ResearchReport]:
        return self.list_all(limit=limit)

    def list_by_asset(self, symbol: str, limit: int = 100) -> List[ResearchReport]:
        return self.get_by_asset(symbol, limit=limit)

    # Backward-compatible aliases for earlier integration drafts.
    def get(self, report_id: str) -> Optional[ResearchReport]:
        return self.get_report(report_id)

    def list_all(self, limit: Optional[int] = None) -> List[ResearchReport]:
        with self._lock:
            records = [self._reports[rid] for rid in self._ordered_ids if rid in self._reports]
        records.sort(key=lambda item: item.created_at, reverse=True)
        if limit is not None:
            return records[:limit]
        return records

    def get_by_asset(self, asset: str, limit: int = 100) -> List[ResearchReport]:
        symbol = asset.strip().upper()
        if not symbol:
            return []
        with self._lock:
            ids = list(self._asset_index.get(symbol, []))
            records = [self._reports[rid] for rid in ids if rid in self._reports]
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[:limit]

    def get_recent(
        self,
        window: timedelta,
        *,
        asset: Optional[str] = None,
        now: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[ResearchReport]:
        if window.total_seconds() < 0:
            raise ValueError("window must be non-negative")

        reference = _to_utc(now) if now is not None else _utc_now()
        cutoff = reference - window

        if asset:
            candidates = self.get_by_asset(asset, limit=max(limit, 1_000))
        else:
            candidates = self.list_all()

        recent = [item for item in candidates if item.created_at >= cutoff]
        recent.sort(key=lambda item: item.created_at, reverse=True)
        return recent[:limit]

    def _prune_if_needed(self) -> None:
        while len(self._ordered_ids) > self.max_reports:
            oldest_id = self._ordered_ids.pop(0)
            old = self._reports.pop(oldest_id, None)
            if old is None:
                continue
            for symbol in old.assets:
                ids = self._asset_index.get(symbol)
                if not ids:
                    continue
                self._asset_index[symbol] = [rid for rid in ids if rid != old.report_id]
                if not self._asset_index[symbol]:
                    self._asset_index.pop(symbol, None)

    def set_event_sink(self, sink: Callable[[dict[str, Any]], Any] | None) -> None:
        self._event_sink = sink

    def _emit_event(self, report: ResearchReport) -> None:
        if self._event_sink is None:
            return
        try:
            self._event_sink(
                {
                    "event_id": report.report_id,
                    "event_type": "research.report.stored",
                    "created_at": report.created_at.isoformat(),
                    "run_id": report.metadata.get("run_id"),
                    "agent_id": report.agent_id,
                    "payload": report.model_dump(mode="json"),
                }
            )
        except Exception:
            pass


# Shared in-process singleton for lightweight orchestration during Phase-1.
research_memory = ResearchMemoryStore()
