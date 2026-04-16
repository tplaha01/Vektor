from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_ts(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat()


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    event_ts: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_ts": self.event_ts,
            "payload": dict(self.payload),
        }


class AuditLog:
    """
    Deterministic in-memory audit log.

    Required contract:
    - record(event_type: str, payload: dict) -> dict
    - query_by_order(order_id: str) -> list[dict]
    - list_blocked(limit: int) -> list[dict]
    """

    def __init__(
        self,
        *,
        clock: Optional[Callable[[], datetime]] = None,
        id_factory: Optional[Callable[[str, int], str]] = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._id_factory = id_factory or self._default_event_id
        self._events: List[AuditEvent] = []
        self._seq = 0
        self._lock = RLock()

    @staticmethod
    def _default_event_id(event_type: str, sequence: int) -> str:
        _ = event_type
        return f"aevt-{sequence:08d}"

    def append_event(
        self,
        *,
        event_type: str,
        outcome: Optional[str] = None,
        blocked_reasons: Optional[Iterable[str]] = None,
        run_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        research_id: Optional[str] = None,
        thesis_id: Optional[str] = None,
        order_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        reasons = tuple(r for r in (blocked_reasons or []) if r)
        with self._lock:
            self._seq += 1
            event = AuditEvent(
                event_id=self._id_factory(event_type, self._seq),
                event_type=event_type,
                event_ts=_format_ts(self._clock()),
                payload={
                    **dict(payload or {}),
                    **({"outcome": outcome} if outcome is not None else {}),
                    **({"blocked_reasons": list(reasons)} if reasons else {}),
                    **({"run_id": run_id} if run_id is not None else {}),
                    **({"decision_id": decision_id} if decision_id is not None else {}),
                    **({"research_id": research_id} if research_id is not None else {}),
                    **({"thesis_id": thesis_id} if thesis_id is not None else {}),
                    **({"order_id": order_id} if order_id is not None else {}),
                    **({"agent_id": agent_id} if agent_id is not None else {}),
                },
            )
            self._events.append(event)
            return event

    def record(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = self.append_event(event_type=event_type, payload=payload)
        return event.to_dict()

    def record_pre_trade_decision(
        self,
        *,
        approved: bool,
        run_id: str | None,
        decision_id: str | None,
        agent_id: str | None,
        blocked_reasons: Optional[Iterable[str]] = None,
        policy_gate_id: Optional[str] = None,
        policy_version: Optional[str] = None,
        research_id: Optional[str] = None,
        thesis_id: Optional[str] = None,
        order_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        reasons = tuple(r for r in (blocked_reasons or []) if r)
        payload = dict(metadata or {})
        if policy_gate_id:
            payload["policy_gate_id"] = policy_gate_id
        if policy_version:
            payload["policy_version"] = policy_version
        return self.append_event(
            event_type="pre_trade.approved" if approved else "pre_trade.rejected",
            outcome="approved" if approved else "rejected",
            blocked_reasons=reasons,
            run_id=run_id or None,
            decision_id=decision_id or None,
            research_id=research_id,
            thesis_id=thesis_id,
            order_id=order_id,
            agent_id=agent_id or None,
            payload=payload,
        )

    def list_events(
        self,
        *,
        limit: Optional[int] = None,
        event_type: Optional[str] = None,
        decision_id: Optional[str] = None,
        order_id: Optional[str] = None,
        run_id: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> List[AuditEvent]:
        with self._lock:
            items = list(self._events)
        if event_type is not None:
            items = [e for e in items if e.event_type == event_type]
        if decision_id is not None:
            items = [e for e in items if e.payload.get("decision_id") == decision_id]
        if order_id is not None:
            items = [e for e in items if e.payload.get("order_id") == order_id]
        if run_id is not None:
            items = [e for e in items if e.payload.get("run_id") == run_id]
        if outcome is not None:
            items = [e for e in items if e.payload.get("outcome") == outcome]
        if limit is not None and limit >= 0:
            items = items[-limit:]
        return items

    def query_by_order(self, order_id: str) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self.list_events(order_id=order_id)]

    def list_blocked(self, limit: int = 100) -> List[Dict[str, Any]]:
        blocked = []
        for event in self.list_events():
            if event.event_type == "pre_trade.rejected":
                blocked.append(event)
                continue
            reasons = event.payload.get("blocked_reasons") or []
            if reasons:
                blocked.append(event)
        if limit is not None and limit >= 0:
            blocked = blocked[-limit:]
        return [event.to_dict() for event in blocked]

    def blocked_reason_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for event in self.list_blocked(limit=10_000):
            for reason in event.get("payload", {}).get("blocked_reasons", []):
                counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: kv[0]))

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._seq = 0


InMemoryAuditLog = AuditLog
audit_log = AuditLog()
