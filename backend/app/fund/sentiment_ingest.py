from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SentimentProvenance(BaseModel):
    source: str = Field(..., description="Origin feed/source, e.g. X, Reuters, OpenClaw.")
    timestamp: datetime = Field(default_factory=_utc_now)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_url: Optional[str] = None
    external_id: Optional[str] = None

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source cannot be empty")
        return value

    @field_validator("timestamp")
    @classmethod
    def _normalize_timestamp(cls, value: datetime) -> datetime:
        return _to_utc(value)


class SentimentSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: str(uuid4()))
    asset: str
    channel: str = Field(..., description="news/social/forum/chat/etc.")
    text: str
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    model_name: Optional[str] = None
    provenance: SentimentProvenance
    created_at: datetime = Field(default_factory=_utc_now)
    metadata: Dict[str, str] = Field(default_factory=dict)

    @field_validator("asset")
    @classmethod
    def _normalize_asset(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("asset cannot be empty")
        return symbol

    @field_validator("channel", "text")
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


class SentimentIngestService:
    """
    In-memory sentiment artifact ingestion store with provenance and lookup helpers.
    """

    def __init__(self, max_artifacts: int = 20000) -> None:
        self.max_artifacts = max_artifacts
        self._lock = RLock()
        self._artifacts: Dict[str, SentimentSnapshot] = {}
        self._ordered_ids: List[str] = []
        self._asset_index: Dict[str, List[str]] = defaultdict(list)

    def ingest(self, snapshot: SentimentSnapshot) -> SentimentSnapshot:
        model = snapshot if isinstance(snapshot, SentimentSnapshot) else SentimentSnapshot.model_validate(snapshot)

        with self._lock:
            existing = self._artifacts.get(model.snapshot_id)
            if existing is None:
                self._ordered_ids.append(model.snapshot_id)
            else:
                ids = self._asset_index.get(existing.asset)
                if ids:
                    self._asset_index[existing.asset] = [aid for aid in ids if aid != existing.snapshot_id]

            self._artifacts[model.snapshot_id] = model
            self._asset_index[model.asset].append(model.snapshot_id)
            self._prune_if_needed()

        return model

    def ingest_many(self, snapshots: Iterable[SentimentSnapshot | dict]) -> List[SentimentSnapshot]:
        saved: List[SentimentSnapshot] = []
        for item in snapshots:
            saved.append(self.ingest(item))
        return saved

    def get(self, snapshot_id: str) -> Optional[SentimentSnapshot]:
        with self._lock:
            return self._artifacts.get(snapshot_id)

    def list_by_asset(self, symbol: str, limit: int = 200) -> List[SentimentSnapshot]:
        symbol = symbol.strip().upper()
        if not symbol:
            return []
        with self._lock:
            ids = list(self._asset_index.get(symbol, []))
            records = [self._artifacts[aid] for aid in ids if aid in self._artifacts]
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[:limit]

    def list_recent(self, limit: int = 200) -> List[SentimentSnapshot]:
        with self._lock:
            candidates = [self._artifacts[aid] for aid in self._ordered_ids if aid in self._artifacts]
        candidates.sort(key=lambda item: item.created_at, reverse=True)
        return candidates[:limit]

    # Helper retained for recent-window queries.
    def get_recent(
        self,
        window: timedelta,
        *,
        asset: Optional[str] = None,
        now: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[SentimentSnapshot]:
        if window.total_seconds() < 0:
            raise ValueError("window must be non-negative")

        reference = _to_utc(now) if now is not None else _utc_now()
        cutoff = reference - window

        if asset:
            candidates = self.list_by_asset(asset, limit=max(limit, 2_000))
        else:
            candidates = self.list_recent(limit=max(limit, 2_000))

        recent = [item for item in candidates if item.created_at >= cutoff]
        recent.sort(key=lambda item: item.created_at, reverse=True)
        return recent[:limit]

    def aggregate_asset_sentiment(self, asset: str, window: timedelta) -> Dict[str, float | int]:
        artifacts = self.get_recent(window, asset=asset, limit=10_000)
        if not artifacts:
            return {"asset": asset.strip().upper(), "count": 0, "weighted_sentiment": 0.0}

        weighted_sum = 0.0
        confidence_sum = 0.0
        for item in artifacts:
            weight = item.provenance.confidence
            weighted_sum += item.sentiment_score * weight
            confidence_sum += weight

        score = weighted_sum / confidence_sum if confidence_sum > 0 else 0.0
        return {
            "asset": artifacts[0].asset,
            "count": len(artifacts),
            "weighted_sentiment": round(score, 6),
        }

    def _prune_if_needed(self) -> None:
        while len(self._ordered_ids) > self.max_artifacts:
            oldest_id = self._ordered_ids.pop(0)
            old = self._artifacts.pop(oldest_id, None)
            if old is None:
                continue
            ids = self._asset_index.get(old.asset)
            if not ids:
                continue
            self._asset_index[old.asset] = [aid for aid in ids if aid != old.snapshot_id]
            if not self._asset_index[old.asset]:
                self._asset_index.pop(old.asset, None)


# Backward-compatible aliases for earlier integration drafts.
SentimentArtifact = SentimentSnapshot
SentimentIngestStore = SentimentIngestService

# Shared in-process singleton for ingestion consumers.
sentiment_ingest = SentimentIngestService()
