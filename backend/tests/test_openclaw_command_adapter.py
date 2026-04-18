from app.fund.audit_log import AuditLog
import app.fund.openclaw_command_adapter as openclaw_adapter_module
from app.fund.openclaw_command_adapter import OpenClawCommandAdapter


class _StubRuntime:
    def __init__(self) -> None:
        self.calls = []
        self.swarm_calls = []
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
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
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


def test_openclaw_command_adapter_rejects_resume_when_halted(monkeypatch):
    runtime = _StubRuntime()
    adapter = OpenClawCommandAdapter(
        runtime=runtime,
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
