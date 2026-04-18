from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    text = str(cursor).strip().lower()
    if not text:
        return 0
    if text.startswith("fes-"):
        text = text[4:]
    try:
        return max(0, int(text))
    except ValueError:
        return 0


class FundRealtimeStream:
    """
    Lightweight in-memory event stream for fund observability endpoints.
    """

    def __init__(self, max_events: int = 10_000) -> None:
        self._lock = RLock()
        self._max_events = max(100, int(max_events))
        self._seq = 0
        self._events: list[dict[str, Any]] = []

    def publish(self, *, source: str, event: dict[str, Any]) -> dict[str, Any]:
        body = dict(event or {})
        with self._lock:
            self._seq += 1
            stream_id = f"fes-{self._seq:08d}"
            wrapped = {
                "stream_id": stream_id,
                "stream_seq": self._seq,
                "stream_source": str(source or "unknown"),
                "stream_published_at": _utc_iso(),
                **body,
            }
            self._events.append(wrapped)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events :]
            return dict(wrapped)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._events)
        if limit < 0:
            return rows
        return rows[-max(1, int(limit)) :]

    def after(self, *, cursor: str | None, limit: int = 200) -> list[dict[str, Any]]:
        cursor_seq = _parse_cursor(cursor)
        rows = []
        with self._lock:
            for event in self._events:
                if int(event.get("stream_seq") or 0) > cursor_seq:
                    rows.append(dict(event))
                    if len(rows) >= max(1, int(limit)):
                        break
        return rows

    def latest_cursor(self) -> str | None:
        with self._lock:
            if not self._events:
                return None
            return str(self._events[-1].get("stream_id"))

    def stats(self) -> dict[str, Any]:
        with self._lock:
            count = len(self._events)
            latest = dict(self._events[-1]) if self._events else None
        return {
            "event_count": count,
            "latest_stream_id": latest.get("stream_id") if latest else None,
            "latest_event_type": latest.get("event_type") if latest else None,
            "latest_run_id": latest.get("run_id") if latest else None,
            "latest_agent_id": latest.get("agent_id") if latest else None,
            "latest_published_at": latest.get("stream_published_at") if latest else None,
            "max_events": self._max_events,
        }


realtime_stream = FundRealtimeStream()
