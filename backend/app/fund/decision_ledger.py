from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Dict, List
from uuid import uuid4

from app.fund.contracts import DecisionRecord


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class DecisionLedger:
    """
    Immutable decision/event ledger with order timeline indexing.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._decisions: Dict[str, DecisionRecord] = {}
        self._events: List[dict[str, Any]] = []
        self._event_sink: Callable[[dict[str, Any]], Any] | None = None

    def add_decision(self, record: DecisionRecord) -> DecisionRecord:
        with self._lock:
            self._decisions[record.decision_id] = record
            self._events.append(
                {
                    "event_id": str(uuid4()),
                    "event_type": "decision_created",
                    "decision_id": record.decision_id,
                    "order_id": None,
                    "ts": _utc_iso(),
                    "payload": record.model_dump(mode="json"),
                }
            )
            self._emit_event(self._events[-1])
        return record

    def update_status(self, decision_id: str, status: str, payload: dict[str, Any] | None = None) -> DecisionRecord | None:
        with self._lock:
            existing = self._decisions.get(decision_id)
            if existing is None:
                return None
            updated = existing.model_copy(update={"status": status})
            self._decisions[decision_id] = updated
            self._events.append(
                {
                    "event_id": str(uuid4()),
                    "event_type": "decision_status_updated",
                    "decision_id": decision_id,
                    "order_id": payload.get("order_id") if payload else None,
                    "ts": _utc_iso(),
                    "payload": payload or {"status": status},
                }
            )
            self._emit_event(self._events[-1])
            return updated

    def add_event(
        self,
        *,
        event_type: str,
        decision_id: str | None,
        order_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "decision_id": decision_id,
            "order_id": order_id,
            "ts": _utc_iso(),
            "payload": payload,
        }
        with self._lock:
            self._events.append(event)
            self._emit_event(event)
        return event

    def pending_decisions(self) -> list[DecisionRecord]:
        with self._lock:
            values = list(self._decisions.values())
        return [item for item in values if item.status in {"proposed"}]

    def blocked_decisions(self) -> list[DecisionRecord]:
        with self._lock:
            values = list(self._decisions.values())
        return [item for item in values if item.status == "blocked"]

    def timeline_for_order(self, order_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = [row for row in self._events if row.get("order_id") == order_id]
        return rows

    def list_events(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._events)
        if limit is not None and limit >= 0:
            return rows[-limit:]
        return rows

    def list_decisions(self) -> list[DecisionRecord]:
        with self._lock:
            return list(self._decisions.values())

    def set_event_sink(self, sink: Callable[[dict[str, Any]], Any] | None) -> None:
        self._event_sink = sink

    def _emit_event(self, event: dict[str, Any]) -> None:
        if self._event_sink is None:
            return
        try:
            self._event_sink(dict(event))
        except Exception:
            pass


decision_ledger = DecisionLedger()
