from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Literal
from uuid import uuid4

from app.fund.contracts import AgentTask

TaskStatus = Literal["queued", "running", "completed", "failed", "blocked"]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TaskBus:
    """
    Lightweight in-memory task bus for Phase-1 orchestration visibility.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._tasks: Dict[str, AgentTask] = {}
        self._history: List[dict[str, Any]] = []

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
        with self._lock:
            self._tasks[task.task_id] = task
            self._history.append(
                {
                    "task_id": task.task_id,
                    "status": task.status,
                    "ts": _utc_iso(),
                    "event": "created",
                }
            )
        return task

    def set_status(self, task_id: str, status: TaskStatus, details: dict[str, Any] | None = None) -> AgentTask | None:
        with self._lock:
            existing = self._tasks.get(task_id)
            if existing is None:
                return None
            updated = existing.model_copy(update={"status": status})
            self._tasks[task_id] = updated
            self._history.append(
                {
                    "task_id": task_id,
                    "status": status,
                    "ts": _utc_iso(),
                    "event": "status_update",
                    "details": details or {},
                }
            )
            return updated

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


task_bus = TaskBus()

