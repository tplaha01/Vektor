from hashlib import sha256
from pathlib import Path

import pytest

from app.fund.audit_log import AuditLog
import app.fund.openclaw_command_adapter as openclaw_adapter_module
from app.fund.openclaw_command_adapter import OpenClawCommandAdapter


def _snapshot_repo_knowledge_graph() -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    kg_root = repo_root / "knowledge_graph"
    events_file = kg_root / "events.jsonl"
    events_dir = kg_root / "events"
    entities_dir = kg_root / "entities"

    events_hash = None
    if events_file.exists():
        events_hash = sha256(events_file.read_bytes()).hexdigest()

    event_md_paths = sorted(
        str(path.relative_to(kg_root))
        for path in events_dir.glob("*.md")
        if path.is_file()
    )
    entity_md_paths = sorted(
        str(path.relative_to(kg_root))
        for path in entities_dir.rglob("*.md")
        if path.is_file()
    )

    return {
        "events_hash": events_hash,
        "event_md_paths": event_md_paths,
        "entity_md_paths": entity_md_paths,
    }


@pytest.fixture(autouse=True)
def _ensure_repo_knowledge_graph_is_unchanged():
    before = _snapshot_repo_knowledge_graph()
    yield
    after = _snapshot_repo_knowledge_graph()
    assert after == before


def _stub_knowledge_graph(monkeypatch):
    captured: list[dict] = []

    def _ingest(**kwargs):
        captured.append(dict(kwargs))
        return {"event_id": "kge-test"}

    monkeypatch.setattr(openclaw_adapter_module.knowledge_graph, "ingest", _ingest)
    return captured


class _StubRuntime:
    def __init__(self) -> None:
        self.calls = []
        self.swarm_calls = []
        self.cancel_run_calls = []
        self.cancel_pack_calls = []
        self.reroute_pack_calls = []
        self.started = True
        self.start_calls = 0
        self.stop_calls = 0
        self.kick_calls = 0

    def enqueue_ceo_command(
        self,
        *,
        run_id: str,
        command: str,
        agent_id: str,
        target_role: str | None,
        payload: dict,
        priority: int,
    ) -> dict:
        self.calls.append(
            {
                "run_id": run_id,
                "command": command,
                "agent_id": agent_id,
                "target_role": target_role,
                "payload": payload,
                "priority": priority,
            }
        )
        return {
            "command_id": "ceocmd-test-1",
            "task_id": "task-test-1",
            "role": target_role or "fund_manager",
            "run_id": run_id,
            "status": "queued",
        }

    def enqueue_signal_swarm(
        self,
        *,
        run_id: str,
        symbol: str,
        agent_id: str,
        command: str,
        payload: dict,
        priority: int,
    ) -> dict:
        self.swarm_calls.append(
            {
                "run_id": run_id,
                "symbol": symbol,
                "agent_id": agent_id,
                "command": command,
                "payload": payload,
                "priority": priority,
            }
        )
        return {
            "command_id": "swarm-test-1",
            "signal_pack_id": "sigpack-test-1",
            "task_ids": ["task-a", "task-b"],
            "role": "signal_swarm",
            "run_id": run_id,
            "status": "queued",
        }

    async def start(self) -> None:
        self.started = True
        self.start_calls += 1

    async def stop(self) -> None:
        self.started = False
        self.stop_calls += 1

    def is_started(self) -> bool:
        return bool(self.started)

    def status(self) -> dict:
        return {
            "started": bool(self.started),
            "autopilot": {"enabled": True, "running": False},
            "data_integrity": {"halted": False, "halt_reason": None},
        }

    def kick_autopilot(self, run_id: str | None = None) -> dict:
        self.kick_calls += 1
        if not self.started:
            return {"accepted": False, "reason": "runtime_not_started"}
        return {"accepted": True, "run_id": run_id or "run-kick-test"}

    def cancel_run(self, *, run_id: str, reason: str = "operator_cancel") -> dict:
        self.cancel_run_calls.append({"run_id": run_id, "reason": reason})
        return {"accepted": True, "run_id": run_id, "blocked_task_count": 2}

    def cancel_signal_pack(self, *, signal_pack_id: str, reason: str = "operator_cancel") -> dict:
        self.cancel_pack_calls.append({"signal_pack_id": signal_pack_id, "reason": reason})
        return {"accepted": True, "signal_pack_id": signal_pack_id, "run_id": "run-pack", "blocked_task_count": 3}

    def reroute_signal_pack(self, *, signal_pack_id: str, assigned_roles: list[str], reason: str = "operator_reroute") -> dict:
        self.reroute_pack_calls.append({"signal_pack_id": signal_pack_id, "assigned_roles": list(assigned_roles), "reason": reason})
        return {"accepted": True, "signal_pack_id": signal_pack_id, "run_id": "run-pack", "assigned_roles": list(assigned_roles)}


class _StubOrchestrator:
    def __init__(self) -> None:
        self.task_history_calls = []
        self.blocked_calls = []
        self.budget_calls = []

    def list_active_tasks(self):
        return [{"task_id": "task-active-1", "run_id": "run-a", "role": "technical_analyst", "status": "running"}]

    def list_task_history(self, *, limit: int = 200, run_id: str | None = None, agent_id: str | None = None, role: str | None = None, status: str | None = None):
        self.task_history_calls.append(
            {"limit": limit, "run_id": run_id, "agent_id": agent_id, "role": role, "status": status}
        )
        return [{"task_id": "task-hist-1", "run_id": run_id or "run-h", "role": role or "fund_manager", "status": status or "completed"}]

    def list_pending_decisions(self):
        return [{"decision_id": "dec-1", "status": "proposed"}]

    def list_blocked_trades(self, limit: int = 100):
        self.blocked_calls.append(limit)
        return [{"decision_id": "dec-blocked-1", "reason": "max_position_exceeded"}]

    def sleeve_budget_status(self, run_id: str | None = None):
        self.budget_calls.append(run_id)
        return {"run_id": run_id, "sleeves": {"tactical": {"remaining_usd": 1000.0}}}

    def knowledge_stats(self):
        return {"event_count": 42, "entity_count": 8}


def test_openclaw_command_adapter_rejects_unauthorized():
    runtime = _StubRuntime()
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        fund_manager_mode=False,
        log=AuditLog(),
    )
    result = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "research aapl",
        },
        token="bad-token",
    )
    assert result["accepted"] is False
    assert result["reason"] == "unauthorized"
    assert runtime.calls == []


def test_openclaw_command_adapter_enforces_channel_and_role_policies():
    runtime = _StubRuntime()
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-research", "vektor-trading"],
        role_allowlist={"insight_researcher", "trader", "fund_manager"},
        channel_role_policies={
            "vektor-research": {"insight_researcher"},
            "vektor-trading": {"trader", "fund_manager"},
        },
        fund_manager_mode=False,
        log=AuditLog(),
    )

    blocked_channel = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "random-chat",
            "sender_name": "ceo",
            "text": "research aapl",
        },
        token="adapter-secret",
    )
    assert blocked_channel["accepted"] is False
    assert blocked_channel["reason"] == "channel_not_allowed"

    blocked_role = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-research",
            "sender_name": "ceo",
            "target_role": "trader",
            "text": "execute trade now",
        },
        token="adapter-secret",
    )
    assert blocked_role["accepted"] is False
    assert blocked_role["reason"] == "role_not_allowed_for_channel"

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-research",
            "sender_name": "ceo",
            "text": "research aapl",
            "run_id": "run-ocmd-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    assert accepted["role"] == "insight_researcher"
    assert len(runtime.calls) == 1


def test_openclaw_command_adapter_routes_swarm_orchestration():
    runtime = _StubRuntime()
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"signal_swarm", "insight_researcher"},
        channel_role_policies={"vektor-ceo": {"signal_swarm", "insight_researcher"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "run full signal swarm on AAPL",
            "run_id": "run-ocmd-swarm-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    assert accepted["role"] == "signal_swarm"
    assert len(runtime.swarm_calls) == 1
    assert runtime.swarm_calls[0]["symbol"] == "AAPL"


def test_openclaw_command_adapter_routes_blog_writer():
    runtime = _StubRuntime()
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"blog_writer", "signal_swarm", "insight_researcher"},
        channel_role_policies={"vektor-ceo": {"blog_writer", "signal_swarm", "insight_researcher"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "write blog post on latest AAPL research insights",
            "run_id": "run-ocmd-blog-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    assert accepted["role"] == "blog_writer"
    assert len(runtime.calls) == 1
    assert runtime.calls[0]["target_role"] == "blog_writer"


def test_openclaw_command_adapter_prioritizes_swarm_over_blog_when_both_present():
    runtime = _StubRuntime()
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"blog_writer", "signal_swarm", "insight_researcher"},
        channel_role_policies={"vektor-ceo": {"blog_writer", "signal_swarm", "insight_researcher"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "run full signal swarm on NVDA and publish a blog",
            "run_id": "run-ocmd-swarm-priority-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    assert accepted["role"] == "signal_swarm"
    assert len(runtime.swarm_calls) == 1
    assert runtime.swarm_calls[0]["symbol"] == "NVDA"


def test_openclaw_command_adapter_fund_manager_mode_routes_analyst_to_swarm():
    runtime = _StubRuntime()
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"signal_swarm", "insight_researcher", "fund_manager"},
        channel_role_policies={"vektor-ceo": {"signal_swarm", "insight_researcher", "fund_manager"}},
        fund_manager_mode=True,
        fund_manager_agent_id="fund_manager",
        fund_manager_assigned_roles={"technical_analyst", "fundamental_analyst", "insight_researcher"},
        log=AuditLog(),
    )

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "research aapl and prepare the execution plan",
            "run_id": "run-ocmd-fm-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    assert accepted["role"] == "signal_swarm"
    assert len(runtime.swarm_calls) == 1
    assert runtime.swarm_calls[0]["agent_id"] == "fund_manager"
    assert sorted(runtime.swarm_calls[0]["payload"]["signal_pack_roles"]) == [
        "fundamental_analyst",
        "insight_researcher",
        "technical_analyst",
    ]


def test_openclaw_command_adapter_routes_runtime_pause_control(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"fund_manager"},
        channel_role_policies={"vektor-ceo": {"fund_manager"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )

    # Ensure strict-halt guard does not block this test.
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: False)
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halt_reason", lambda: None)

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "pause runtime now",
            "run_id": "run-ocmd-control-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    assert accepted["role"] == "runtime_control"
    assert accepted["route_result"]["action"] == "pause_runtime"
    assert accepted["route_result"]["status"] in {"pausing", "already_paused"}
    assert runtime.stop_calls == 1
    assert knowledge_events
    assert knowledge_events[-1]["event_type"] == "runtime.control.pause_runtime"


def test_openclaw_command_adapter_rejects_resume_when_halted(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"fund_manager"},
        channel_role_policies={"vektor-ceo": {"fund_manager"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )

    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: True)
    monkeypatch.setattr(
        openclaw_adapter_module.data_integrity_guard,
        "halt_reason",
        lambda: "real_data_required:test_provider:fallback",
    )

    rejected = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "resume runtime",
            "run_id": "run-ocmd-control-2",
        },
        token="adapter-secret",
    )
    assert rejected["accepted"] is False
    assert rejected["reason"] == "real_data_required:test_provider:fallback"
    if knowledge_events:
        assert knowledge_events[-1]["event_type"] == "runtime.control.resume_runtime"


def test_openclaw_command_adapter_routes_runtime_status_control(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    runtime.started = False
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"fund_manager"},
        channel_role_policies={"vektor-ceo": {"fund_manager"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: True)
    monkeypatch.setattr(
        openclaw_adapter_module.data_integrity_guard,
        "halt_reason",
        lambda: "real_data_required:test_provider:fallback",
    )

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "runtime status",
            "run_id": "run-ocmd-control-status-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    route_result = accepted["route_result"]
    assert route_result["action"] == "runtime_status"
    assert route_result["status"] == "reported"
    assert route_result["runtime_started"] is False
    assert route_result["halted"] is True
    assert route_result["halt_reason"] == "real_data_required:test_provider:fallback"
    assert knowledge_events[-1]["event_type"] == "runtime.control.runtime_status"


def test_openclaw_command_adapter_routes_clear_halt_control(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"fund_manager"},
        channel_role_policies={"vektor-ceo": {"fund_manager"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: True)
    monkeypatch.setattr(
        openclaw_adapter_module.data_integrity_guard,
        "clear_halt",
        lambda *, reason: {
            "cleared": True,
            "cleared_at": "2026-04-17T00:00:00Z",
            "reason": reason,
            "previous_halt_reason": "real_data_required:test_provider:fallback",
            "previous_halted_at": "2026-04-17T00:00:00Z",
        },
    )

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "clear halt",
            "run_id": "run-ocmd-control-clear-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    route_result = accepted["route_result"]
    assert route_result["action"] == "clear_halt"
    assert route_result["status"] == "halt_cleared"
    assert route_result["clear_result"]["cleared"] is True
    assert knowledge_events[-1]["event_type"] == "runtime.control.clear_halt"


def test_openclaw_command_adapter_routes_kick_autopilot_control(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"fund_manager"},
        channel_role_policies={"vektor-ceo": {"fund_manager"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: False)
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halt_reason", lambda: None)

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "kick autopilot",
            "run_id": "run-ocmd-control-kick-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    route_result = accepted["route_result"]
    assert route_result["action"] == "kick_autopilot"
    assert route_result["status"] == "accepted"
    assert runtime.kick_calls == 1
    assert knowledge_events[-1]["event_type"] == "runtime.control.kick_autopilot"


def test_openclaw_command_adapter_routes_task_history_control(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"fund_manager"},
        channel_role_policies={"vektor-ceo": {"fund_manager"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: False)
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halt_reason", lambda: None)

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "task history run_id=run-123 role=technical_analyst status=completed limit=25",
            "run_id": "run-ocmd-control-history-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    route_result = accepted["route_result"]
    assert route_result["action"] == "task_history"
    assert route_result["status"] == "reported"
    assert route_result["limit"] == 25
    assert route_result["count"] == 1
    assert orchestrator.task_history_calls[-1] == {
        "limit": 25,
        "run_id": "run-123",
        "agent_id": None,
        "role": "technical_analyst",
        "status": "completed",
    }
    assert knowledge_events[-1]["event_type"] == "runtime.control.task_history"


def test_openclaw_command_adapter_routes_pending_decisions_control(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["vektor-ceo"],
        role_allowlist={"fund_manager"},
        channel_role_policies={"vektor-ceo": {"fund_manager"}},
        fund_manager_mode=False,
        log=AuditLog(),
    )
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: False)
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halt_reason", lambda: None)

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "vektor-ceo",
            "sender_name": "ceo",
            "text": "pending decisions",
            "run_id": "run-ocmd-control-pending-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    route_result = accepted["route_result"]
    assert route_result["action"] == "pending_decisions"
    assert route_result["status"] == "reported"
    assert route_result["count"] == 1
    assert route_result["decisions"][0]["decision_id"] == "dec-1"
    assert knowledge_events[-1]["event_type"] == "runtime.control.pending_decisions"


def test_openclaw_command_adapter_reroutes_signal_pack_roles(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["general"],
        sender_allowlist=["ceo"],
        fund_manager_mode=True,
        log=AuditLog(),
    )
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: False)
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halt_reason", lambda: None)

    accepted = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "general",
            "sender_name": "ceo",
            "text": "reroute signal pack pack:sigpack-123 roles=technical_analyst,sentiment_analyst",
            "run_id": "run-ocmd-reroute-1",
        },
        token="adapter-secret",
    )
    assert accepted["accepted"] is True
    route_result = accepted["route_result"]
    assert route_result["action"] == "reroute_signal_pack"
    assert runtime.reroute_pack_calls[0]["signal_pack_id"] == "sigpack-123"
    assert runtime.reroute_pack_calls[0]["assigned_roles"] == ["technical_analyst", "sentiment_analyst"]
    assert runtime.reroute_pack_calls[0]["reason"].startswith("openclaw:")
    assert knowledge_events[-1]["event_type"] == "runtime.control.reroute_signal_pack"


def test_openclaw_command_adapter_cancels_run_and_pack(monkeypatch):
    runtime = _StubRuntime()
    orchestrator = _StubOrchestrator()
    knowledge_events = _stub_knowledge_graph(monkeypatch)
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
        orchestrator=orchestrator,
        token="adapter-secret",
        enabled=True,
        channel_allowlist=["general"],
        sender_allowlist=["ceo"],
        fund_manager_mode=True,
        log=AuditLog(),
    )
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halted", lambda: False)
    monkeypatch.setattr(openclaw_adapter_module.data_integrity_guard, "halt_reason", lambda: None)

    cancel_run = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "general",
            "sender_name": "ceo",
            "text": "cancel run run:run-ocmd-cancel",
            "run_id": "run-ocmd-control-1",
        },
        token="adapter-secret",
    )
    cancel_pack = adapter.route_message(
        {
            "platform": "discord",
            "channel_name": "general",
            "sender_name": "ceo",
            "text": "cancel signal pack pack:sigpack-999",
            "run_id": "run-ocmd-control-1",
        },
        token="adapter-secret",
    )
    assert cancel_run["accepted"] is True
    assert cancel_pack["accepted"] is True
    assert runtime.cancel_run_calls[0]["run_id"] == "run-ocmd-cancel"
    assert runtime.cancel_run_calls[0]["reason"].startswith("openclaw:")
    assert runtime.cancel_pack_calls[0]["signal_pack_id"] == "sigpack-999"
    assert runtime.cancel_pack_calls[0]["reason"].startswith("openclaw:")
    assert knowledge_events[-2]["event_type"] == "runtime.control.cancel_run"
    assert knowledge_events[-1]["event_type"] == "runtime.control.cancel_signal_pack"
