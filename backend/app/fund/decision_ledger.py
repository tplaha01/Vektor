from __future__ import annotations

from datetime import datetime, timezone
import logging
from threading import RLock
from typing import Any, Callable, Dict, List
from uuid import uuid4

from app.fund.contracts import DecisionRecord

logger = logging.getLogger("alfred.fund.decision_ledger")


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
            self._persist_decision(record)
            self._persist_event(self._events[-1])
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
            self._persist_decision(updated)
            self._persist_event(self._events[-1])
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
            self._persist_event(event)
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

    def restore_from_storage(self) -> dict[str, int]:
        try:
            from app.storage import db as storage_db

            loaded_decisions = storage_db.load_decision_records()
            loaded_events = storage_db.load_decision_events()
        except Exception as exc:
            logger.warning("decision_ledger.restore_failed: %s", exc)
            return {"restored": 0, "decisions": len(self._decisions), "events": len(self._events)}

        restored_decisions: Dict[str, DecisionRecord] = {}
        restored_events: List[dict[str, Any]] = []

        for row in loaded_decisions:
            try:
                model = DecisionRecord.model_validate(row)
            except Exception:
                continue
            restored_decisions[model.decision_id] = model

        for row in loaded_events:
            if not isinstance(row, dict):
                continue
            restored_events.append(dict(row))

        restored_events.sort(key=lambda item: str(item.get("ts") or ""))

        with self._lock:
            self._decisions = restored_decisions
            self._events = restored_events

        return {"restored": 1, "decisions": len(restored_decisions), "events": len(restored_events)}

    def _persist_decision(self, record: DecisionRecord) -> None:
        try:
            from app.storage import db as storage_db

            storage_db.save_decision_record(record.model_dump(mode="json"))
        except Exception as exc:
            logger.debug("decision_ledger.persist_decision_failed: %s", exc)

    def _persist_event(self, event: dict[str, Any]) -> None:
        try:
            from app.storage import db as storage_db

            storage_db.save_decision_event(dict(event))
        except Exception as exc:
            logger.debug("decision_ledger.persist_event_failed: %s", exc)

    def _emit_event(self, event: dict[str, Any]) -> None:
        if self._event_sink is None:
            return
        try:
            self._event_sink(dict(event))
        except Exception:
            pass


decision_ledger = DecisionLedger()
