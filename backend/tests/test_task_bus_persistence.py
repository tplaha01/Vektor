from app.config import get_settings
from app.fund.task_bus import TaskBus
from app.storage import db as storage_db


def test_task_bus_persists_events_and_propagates_symbol_reason(monkeypatch):
    persisted_rows: list[dict] = []

    def _save(row):  # noqa: ANN001
        persisted_rows.append(dict(row))

    monkeypatch.setattr(storage_db, "save_task_history_event", _save)

    bus = TaskBus()
    task = bus.create_task(
        run_id="run-taskbus-1",
        agent_id="ceo",
        role="technical_analyst",
        payload={"symbol": "AAPL", "signal_pack_id": "sigpack-1"},
        priority=9,
    )
    bus.set_status(task.task_id, "failed", {"error": "upstream_timeout"})

    history = bus.history(limit=-1)
    assert len(history) == 2
    created = history[0]
    assert created["event"] == "created"
    assert created["details"]["symbol"] == "AAPL"
    assert created["details"]["signal_pack_id"] == "sigpack-1"

    failed = history[-1]
    assert failed["event"] == "status_update"
    assert failed["details"]["symbol"] == "AAPL"
    assert failed["details"]["signal_pack_id"] == "sigpack-1"
    assert failed["details"]["reason"] == "upstream_timeout"
    assert failed["details"]["reasons"] == ["upstream_timeout"]

    assert len(persisted_rows) == 2
    assert persisted_rows[0]["event"] == "created"
    assert persisted_rows[1]["event"] == "status_update"


def test_task_bus_restore_preserves_history_without_reviving_live_tasks(monkeypatch):
    rows = [
        {
            "task_id": "task-1",
            "run_id": "run-restore-1",
            "agent_id": "ceo",
            "role": "insight_researcher",
            "status": "queued",
            "event": "created",
            "ts": "2026-04-17T00:00:00Z",
            "priority": 7,
            "payload": {"symbol": "MSFT"},
        },
        {
            "task_id": "task-1",
            "run_id": "run-restore-1",
            "agent_id": "ceo",
            "role": "insight_researcher",
            "status": "running",
            "event": "claimed",
            "ts": "2026-04-17T00:00:01Z",
            "details": {"role": "insight_researcher"},
        },
        {
            "task_id": "task-1",
            "run_id": "run-restore-1",
            "agent_id": "ceo",
            "role": "insight_researcher",
            "status": "completed",
            "event": "status_update",
            "ts": "2026-04-17T00:00:02Z",
            "details": {"report_id": "report-1"},
        },
    ]

    monkeypatch.setattr(storage_db, "load_task_history_events", lambda limit=None: rows)
    bus = TaskBus()
    restored = bus.restore_from_storage()
    assert restored["restored"] is True
    assert restored["event_count"] == 3
    assert restored["task_count"] == 0

    task = bus.get_task("task-1")
    assert task is None
    history = bus.history(limit=-1)
    assert history[-1]["status"] == "completed"
    assert history[0]["payload"]["symbol"] == "MSFT"
    assert bus.active_tasks() == []


def test_task_bus_block_queued_preserves_symbol_and_reason(monkeypatch):
    persisted_rows: list[dict] = []

    def _save(row):  # noqa: ANN001
        persisted_rows.append(dict(row))

    monkeypatch.setattr(storage_db, "save_task_history_event", _save)

    bus = TaskBus()
    queued = bus.create_task(
        run_id="run-halt-1",
        agent_id="autopilot_coordinator",
        role="technical_analyst",
        payload={"symbol": "NVDA", "signal_pack_id": "sigpack-halt-1"},
        priority=7,
    )
    bus.block_queued(reason="real_data_required:finnhub_news:fallback")

    task = bus.get_task(queued.task_id)
    assert task is not None
    assert task.status == "blocked"

    blocked_rows = [
        row
        for row in bus.history(limit=-1)
        if row.get("event") == "status_update" and row.get("status") == "blocked"
    ]
    assert len(blocked_rows) == 1
    blocked = blocked_rows[0]
    assert blocked["details"]["symbol"] == "NVDA"
    assert blocked["details"]["reason"] == "real_data_required:finnhub_news:fallback"
    assert blocked["details"]["reasons"] == ["real_data_required:finnhub_news:fallback"]

    assert any(row.get("status") == "blocked" for row in persisted_rows)


def test_task_bus_deferred_task_waits_until_next_attempt(monkeypatch):
    persisted_rows: list[dict] = []

    def _save(row):  # noqa: ANN001
        persisted_rows.append(dict(row))

    monkeypatch.setattr(storage_db, "save_task_history_event", _save)

    bus = TaskBus()
    task = bus.create_task(
        run_id="run-defer-1",
        agent_id="ceo",
        role="technical_analyst",
        payload={"symbol": "NVDA"},
        priority=8,
    )
    bus.claim_next_queued("technical_analyst")
    deferred = bus.defer_task(
        task.task_id,
        reason="gemini_flash_lite:provider_cooling_down:40.0s | groq:provider_cooling_down:25.0s",
        retry_after_seconds=2.0,
        extra_details={"providers": ["gemini_flash_lite", "groq"]},
    )

    assert deferred is not None
    assert deferred.status == "queued"
    scheduler = deferred.payload.get("_scheduler")
    assert isinstance(scheduler, dict)
    assert scheduler["retry_count"] == 1
    assert scheduler["next_attempt_at"]

    assert bus.claim_next_queued("technical_analyst") is None

    scheduler["next_attempt_at"] = "2026-01-01T00:00:00Z"
    ready = bus.claim_next_queued("technical_analyst")
    assert ready is not None
    assert ready.task_id == task.task_id

    deferred_rows = [row for row in bus.history(limit=-1) if row.get("event") == "deferred"]
    assert len(deferred_rows) == 1
    assert deferred_rows[0]["details"]["next_attempt_at"]
    assert deferred_rows[0]["details"]["retry_count"] == 1
    assert any(row.get("event") == "deferred" for row in persisted_rows)


def test_task_bus_exponential_defer_backoff_increases_retry_window(monkeypatch):
    monkeypatch.setenv("AI_ROLE_DEFER_BASE_SECONDS", "5")
    monkeypatch.setenv("AI_ROLE_DEFER_BACKOFF_MULTIPLIER", "2")
    monkeypatch.setenv("AI_ROLE_DEFER_MAX_SECONDS", "60")
    get_settings.cache_clear()

    bus = TaskBus()
    task = bus.create_task(
        run_id="run-defer-backoff-1",
        agent_id="ceo",
        role="technical_analyst",
        payload={"symbol": "SPY"},
        priority=7,
    )
    bus.claim_next_queued("technical_analyst")
    first = bus.defer_task(task.task_id, reason="provider_cooling_down", retry_after_seconds=2.0)
    second = bus.defer_task(task.task_id, reason="provider_cooling_down", retry_after_seconds=2.0)

    first_scheduler = dict(first.payload.get("_scheduler") or {})
    second_scheduler = dict(second.payload.get("_scheduler") or {})
    assert float(first_scheduler["retry_after_seconds"]) == 5.0
    assert float(second_scheduler["retry_after_seconds"]) == 10.0
    get_settings.cache_clear()
