from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Dict, List, Literal
from uuid import uuid4

from app.config import get_settings
from app.fund.contracts import AgentTask
from app.websocket.agent_events import publish_agent_event

TaskStatus = Literal["queued", "running", "completed", "failed", "blocked"]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso_utc(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _defer_delay_seconds(*, retry_count: int, suggested_retry_after_seconds: float) -> float:
    settings = get_settings()
    base = max(1.0, float(settings.AI_ROLE_DEFER_BASE_SECONDS))
    multiplier = max(1.0, float(settings.AI_ROLE_DEFER_BACKOFF_MULTIPLIER))
    ceiling = max(base, float(settings.AI_ROLE_DEFER_MAX_SECONDS))
    exponential = base * (multiplier ** max(0, int(retry_count) - 1))
    return max(1.0, min(ceiling, max(float(suggested_retry_after_seconds), exponential)))


class TaskBus:
    """
    Lightweight in-memory task bus for Phase-1 orchestration visibility.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._tasks: Dict[str, AgentTask] = {}
        self._history: List[dict[str, Any]] = []
        self._event_sink: Callable[[dict[str, Any]], Any] | None = None

    def restore_from_storage(self, *, limit: int | None = None) -> dict[str, Any]:
        try:
            from app.storage import db as storage_db

            rows = storage_db.load_task_history_events(limit=limit)
        except Exception:
            return {"restored": False, "event_count": 0, "task_count": len(self._tasks)}

        with self._lock:
            self._history = [dict(row) for row in rows]
            # Persisted history must survive restarts, but restoring queued/running/blocked
            # tasks as "live" causes stale demo and old halted work to reappear in the UI.
            # Live task state is rebuilt only from the current runtime after startup.
            self._tasks = {}

        return {"restored": True, "event_count": len(self._history), "task_count": len(self._tasks)}

    def create_task(
        self,
        *,
        run_id: str,
        agent_id: str,
        role: str,
        payload: dict[str, Any] | None = None,
        priority: int = 5,
    ) -> AgentTask:
        task = AgentTask(
            task_id=str(uuid4()),
            run_id=run_id,
            agent_id=agent_id,
            role=role,
            status="queued",
            priority=priority,
            payload=payload or {},
            created_at=_utc_iso(),
        )
        row: dict[str, Any]
        event_payload: dict[str, Any]
        with self._lock:
            self._tasks[task.task_id] = task
            normalized_details = self._normalize_details(task, status=task.status, details={})
            row = {
                "task_id": task.task_id,
                "run_id": task.run_id,
                "agent_id": task.agent_id,
                "role": task.role,
                "status": task.status,
                "ts": _utc_iso(),
                "event": "created",
                "priority": task.priority,
                "details": normalized_details,
                "payload": dict(task.payload or {}),
            }
            self._history.append(row)
            event_payload = {
                "event_id": task.task_id,
                "event_type": "task.created",
                "ts": task.created_at,
                "run_id": task.run_id,
                "agent_id": task.agent_id,
                "payload": task.model_dump(mode="json"),
            }
        self._persist_history_row(row)
        self._emit_event(event_payload)
        return task

    def set_status(self, task_id: str, status: TaskStatus, details: dict[str, Any] | None = None) -> AgentTask | None:
        row: dict[str, Any]
        event_payload: dict[str, Any]
        with self._lock:
            existing = self._tasks.get(task_id)
            if existing is None:
                return None
            updated = existing.model_copy(update={"status": status})
            self._tasks[task_id] = updated
            normalized_details = self._normalize_details(updated, status=status, details=details)
            row = {
                "task_id": task_id,
                "run_id": updated.run_id,
                "agent_id": updated.agent_id,
                "role": updated.role,
                "status": status,
                "ts": _utc_iso(),
                "event": "status_update",
                "details": normalized_details,
            }
            self._history.append(row)
            event_payload = {
                "event_id": f"{task_id}:{status}:{len(self._history)}",
                "event_type": "task.status_updated",
                "ts": _utc_iso(),
                "run_id": updated.run_id,
                "agent_id": updated.agent_id,
                "decision_id": (details or {}).get("decision_id"),
                "payload": {
                    "task_id": task_id,
                    "status": status,
                    "details": normalized_details,
                    "role": updated.role,
                },
            }
        self._persist_history_row(row)
        self._emit_event(event_payload)
        return updated

    def claim_next_queued(self, role: str) -> AgentTask | None:
        """
        Atomically claim the highest-priority queued task for a role.
        Claimed task status is set to running.
        """
        row: dict[str, Any]
        event_payload: dict[str, Any]
        with self._lock:
            candidates = [
                task
                for task in self._tasks.values()
                if task.role == role and task.status == "queued" and self._task_ready(task)
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda item: (-item.priority, item.created_at, item.task_id))
            selected = candidates[0]
            updated = selected.model_copy(update={"status": "running"})
            self._tasks[selected.task_id] = updated
            claim_details = self._normalize_details(updated, status="running", details={"role": role})
            row = {
                "task_id": selected.task_id,
                "run_id": selected.run_id,
                "agent_id": selected.agent_id,
                "role": selected.role,
                "status": "running",
                "ts": _utc_iso(),
                "event": "claimed",
                "details": claim_details,
            }
            self._history.append(row)
            event_payload = {
                "event_id": f"{selected.task_id}:claimed:{len(self._history)}",
                "event_type": "task.claimed",
                "ts": _utc_iso(),
                "run_id": updated.run_id,
                "agent_id": updated.agent_id,
                "payload": {
                    "task_id": selected.task_id,
                    "role": role,
                },
            }
        self._persist_history_row(row)
        self._emit_event(event_payload)
        return updated

    def defer_task(
        self,
        task_id: str,
        *,
        reason: str,
        retry_after_seconds: float,
        extra_details: dict[str, Any] | None = None,
    ) -> AgentTask | None:
        row: dict[str, Any]
        event_payload: dict[str, Any]
        now_iso = _utc_iso()
        with self._lock:
            existing = self._tasks.get(task_id)
            if existing is None:
                return None
            payload = dict(existing.payload or {})
            scheduler = dict(payload.get("_scheduler") or {})
            retry_count = int(scheduler.get("retry_count") or 0) + 1
            retry_after_seconds = _defer_delay_seconds(
                retry_count=retry_count,
                suggested_retry_after_seconds=max(1.0, float(retry_after_seconds)),
            )
            next_attempt_dt = datetime.now(timezone.utc).timestamp() + retry_after_seconds
            next_attempt_at = _utc_iso_from_timestamp(next_attempt_dt)
            scheduler.update(
                {
                    "retry_count": retry_count,
                    "deferred_at": now_iso,
                    "next_attempt_at": next_attempt_at,
                    "retry_after_seconds": round(retry_after_seconds, 2),
                    "reason": str(reason or "temporarily_unavailable"),
                }
            )
            payload["_scheduler"] = scheduler
            updated = existing.model_copy(update={"status": "queued", "payload": payload})
            self._tasks[task_id] = updated
            normalized_details = self._normalize_details(
                updated,
                status="queued",
                details={
                    "reason": str(reason or "temporarily_unavailable"),
                    "retry_after_seconds": round(retry_after_seconds, 2),
                    "next_attempt_at": next_attempt_at,
                    "deferred_at": now_iso,
                    "retry_count": retry_count,
                    **dict(extra_details or {}),
                },
            )
            row = {
                "task_id": task_id,
                "run_id": updated.run_id,
                "agent_id": updated.agent_id,
                "role": updated.role,
                "status": "queued",
                "ts": now_iso,
                "event": "deferred",
                "details": normalized_details,
                "payload": dict(updated.payload or {}),
            }
            self._history.append(row)
            event_payload = {
                "event_id": f"{task_id}:deferred:{len(self._history)}",
                "event_type": "task.deferred",
                "ts": now_iso,
                "run_id": updated.run_id,
                "agent_id": updated.agent_id,
                "decision_id": normalized_details.get("decision_id"),
                "payload": {
                    "task_id": task_id,
                    "status": "queued",
                    "details": normalized_details,
                    "role": updated.role,
                },
            }
        self._persist_history_row(row)
        self._emit_event(event_payload)
        return updated

    def block_queued(
        self,
        *,
        reason: str,
        roles: list[str] | None = None,
        extra_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Bulk-block queued tasks. Used by runtime safety guardrails when the system is halted.
        """
        normalized_reason = str(reason or "system_halted").strip() or "system_halted"
        role_filter = {str(item).strip() for item in (roles or []) if str(item).strip()}
        blocked_ids: list[str] = []
        rows_to_persist: list[dict[str, Any]] = []
        events_to_emit: list[dict[str, Any]] = []

        with self._lock:
            for task_id, task in list(self._tasks.items()):
                if task.status != "queued":
                    continue
                if role_filter and task.role not in role_filter:
                    continue

                updated = task.model_copy(update={"status": "blocked"})
                self._tasks[task_id] = updated
                details = {"reason": normalized_reason, "reasons": [normalized_reason], **dict(extra_details or {})}
                normalized_details = self._normalize_details(updated, status="blocked", details=details)
                row = {
                    "task_id": task_id,
                    "run_id": updated.run_id,
                    "agent_id": updated.agent_id,
                    "role": updated.role,
                    "status": "blocked",
                    "ts": _utc_iso(),
                    "event": "status_update",
                    "details": normalized_details,
                }
                self._history.append(row)
                rows_to_persist.append(row)
                events_to_emit.append(
                    {
                        "event_id": f"{task_id}:blocked:{len(self._history)}",
                        "event_type": "task.status_updated",
                        "ts": row["ts"],
                        "run_id": updated.run_id,
                        "agent_id": updated.agent_id,
                        "decision_id": normalized_details.get("decision_id"),
                        "payload": {
                            "task_id": task_id,
                            "status": "blocked",
                            "details": normalized_details,
                            "role": updated.role,
                        },
                    }
                )
                blocked_ids.append(task_id)

        for row in rows_to_persist:
            self._persist_history_row(row)
        for event in events_to_emit:
            self._emit_event(event)

        return {"blocked_count": len(blocked_ids), "task_ids": blocked_ids, "reason": normalized_reason}

    def active_tasks(self) -> list[AgentTask]:
        with self._lock:
            items = list(self._tasks.values())
        return [
            task
            for task in items
            if task.status in {"queued", "running", "blocked"}
        ]

    def get_task(self, task_id: str) -> AgentTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def history(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._history)
        if limit < 0:
            return rows
        return rows[-limit:]

    def query_history(
        self,
        *,
        limit: int = 200,
        run_id: str | None = None,
        agent_id: str | None = None,
        role: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Filter task history without copying/scanning the full list in normal limited queries.
        Scans from newest backward and stops once limit is satisfied.
        """
        max_items = None if limit < 0 else max(1, int(limit))
        out: list[dict[str, Any]] = []
        with self._lock:
            for row in reversed(self._history):
                if run_id and row.get("run_id") != run_id:
                    continue
                if agent_id and row.get("agent_id") != agent_id:
                    continue
                if role and row.get("role") != role:
                    continue
                if status and row.get("status") != status:
                    continue
                out.append(dict(row))
                if max_items is not None and len(out) >= max_items:
                    break
        out.reverse()
        return out

    def list_tasks(self) -> list[AgentTask]:
        with self._lock:
            return list(self._tasks.values())

    def set_event_sink(self, sink: Callable[[dict[str, Any]], Any] | None) -> None:
        self._event_sink = sink

    def _emit_event(self, event: dict[str, Any]) -> None:
        event_copy = dict(event)
        
        # Emit to legacy event sink
        if self._event_sink is not None:
            try:
                self._event_sink(event_copy)
            except Exception:
                pass
        
        # Publish to WebSocket stream for real-time clients
        try:
            event_type = event_copy.get("event_type", "unknown")
            publish_agent_event(event_type, event_copy)
        except Exception:
            pass

    def _persist_history_row(self, row: dict[str, Any]) -> None:
        try:
            from app.storage import db as storage_db

            storage_db.save_task_history_event(row)
        except Exception:
            pass

    def _rebuild_tasks_from_history(self, rows: list[dict[str, Any]]) -> Dict[str, AgentTask]:
        rebuilt: Dict[str, AgentTask] = {}
        for row in rows:
            task_id = str(row.get("task_id") or "").strip()
            if not task_id:
                continue
            run_id = str(row.get("run_id") or "").strip()
            agent_id = str(row.get("agent_id") or "").strip()
            role = str(row.get("role") or "").strip()
            status = str(row.get("status") or "queued").strip().lower() or "queued"
            ts = str(row.get("ts") or _utc_iso())
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            priority = 5
            try:
                priority = int(row.get("priority") if row.get("priority") is not None else payload.get("priority", 5))
            except Exception:
                priority = 5

            if task_id not in rebuilt:
                rebuilt[task_id] = AgentTask(
                    task_id=task_id,
                    run_id=run_id,
                    agent_id=agent_id,
                    role=role,
                    status=status if status in {"queued", "running", "completed", "failed", "blocked"} else "queued",
                    priority=priority,
                    payload=payload,
                    created_at=ts,
                )
                continue
            existing = rebuilt[task_id]
            rebuilt[task_id] = existing.model_copy(
                update={
                    "status": status if status in {"queued", "running", "completed", "failed", "blocked"} else existing.status,
                    "run_id": run_id or existing.run_id,
                    "agent_id": agent_id or existing.agent_id,
                    "role": role or existing.role,
                }
            )
        return rebuilt

    def _normalize_details(self, task: AgentTask, *, status: TaskStatus, details: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(details or {})
        payload = dict(task.payload or {})

        def _fill_from_payload(key: str) -> None:
            if merged.get(key) in {None, ""} and payload.get(key) not in {None, ""}:
                merged[key] = payload.get(key)

        for key in ("symbol", "side", "quantity", "price", "signal_pack_id", "decision_id", "thesis_id", "order_id"):
            _fill_from_payload(key)

        if merged.get("symbol") in {None, ""} and payload.get("asset") not in {None, ""}:
            merged["symbol"] = payload.get("asset")

        if status in {"failed", "blocked"}:
            reason = merged.get("reason")
            if reason in {None, ""}:
                reasons = merged.get("reasons")
                if isinstance(reasons, list) and reasons:
                    reason = reasons[0]
            if reason in {None, ""}:
                reason = merged.get("error")
            if reason in {None, ""}:
                reason = payload.get("reason")
            if reason in {None, ""}:
                reason = "unspecified"
            merged["reason"] = str(reason)
            reasons = merged.get("reasons")
            if not isinstance(reasons, list) or not reasons:
                merged["reasons"] = [str(reason)]

        return merged

    def _task_ready(self, task: AgentTask) -> bool:
        payload = dict(task.payload or {})
        scheduler = payload.get("_scheduler") if isinstance(payload.get("_scheduler"), dict) else {}
        next_attempt = _parse_iso_utc(scheduler.get("next_attempt_at"))
        if next_attempt is None:
            return True
        return next_attempt <= datetime.now(timezone.utc)


def _utc_iso_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(float(value), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


task_bus = TaskBus()
