from __future__ import annotations

import asyncio
import os
import secrets
import re
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Set
from uuid import uuid4

from app.config import get_settings
from app.fund.agent_runtime import FundAgentRuntime, fund_agent_runtime
from app.fund.audit_log import AuditLog, audit_log
from app.fund.knowledge_graph import knowledge_graph
from app.fund.runtime_guard import data_integrity_guard


ALLOWED_ROLES: tuple[str, ...] = (
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_timeseries_analyst",
    "insight_researcher",
    "hedge_fund_researcher",
    "fund_manager",
    "trader",
    "risk_auditor",
    "signal_swarm",
    "blog_writer",
)

ANALYST_ROLES: tuple[str, ...] = (
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_timeseries_analyst",
    "insight_researcher",
    "hedge_fund_researcher",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    parts = [item.strip().lower() for item in value.split(",")]
    return {item for item in parts if item}


def _parse_channel_role_policies(value: str | None, role_allowlist: set[str]) -> dict[str, set[str]]:
    """
    Syntax:
    channelA=technical_analyst,insight_researcher;channelB=trader,fund_manager
    """
    policies: dict[str, set[str]] = {}
    if not value:
        return policies
    for item in value.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, raw_roles = item.split("=", 1)
        channel_key = key.strip().lower()
        roles = {role.strip().lower() for role in raw_roles.split(",") if role.strip()}
        allowed = {role for role in roles if role in role_allowlist}
        if channel_key and allowed:
            policies[channel_key] = allowed
    return policies


def _infer_role(command: str) -> str:
    text = command.lower()
    if "research" in text and any(key in text for key in ("trade", "execute", "position", "portfolio")):
        return "signal_swarm"
    if any(key in text for key in ("blog", "publish post", "write post", "write article", "newsletter")):
        return "blog_writer"
    if any(key in text for key in ("swarm", "multi-signal", "full signal", "signal pack")):
        return "signal_swarm"
    if any(key in text for key in ("technical", "rsi", "macd", "ema", "atr")):
        return "technical_analyst"
    if any(key in text for key in ("fundamental", "valuation", "earnings", "fmp")):
        return "fundamental_analyst"
    if any(key in text for key in ("sentiment", "news", "x ", "twitter", "social")):
        return "sentiment_analyst"
    if any(key in text for key in ("ml", "timeseries", "forecast", "model")):
        return "ml_timeseries_analyst"
    if any(key in text for key in ("insight", "narrative", "research")):
        return "insight_researcher"
    if any(key in text for key in ("macro", "scenario", "hedge fund")):
        return "hedge_fund_researcher"
    if "risk" in text or "audit" in text or "compliance" in text:
        return "risk_auditor"
    if "trade" in text or "execute" in text or "entry" in text or "exit" in text:
        return "trader"
    return "fund_manager"


def _extract_symbol(text: str) -> str | None:
    tokens = re.findall(r"\b[A-Z]{1,6}\b", str(text or "").upper())
    ignored = {
        "RUN",
        "FULL",
        "SIGNAL",
        "SWARM",
        "ON",
        "AND",
        "BUY",
        "SELL",
        "TRADE",
        "RESEARCH",
        "NOW",
    }
    for token in tokens:
        if token not in ignored:
            return token
    return None


def _parse_control_command(command: str) -> dict[str, Any] | None:
    text = str(command or "").strip().lower()
    normalized = re.sub(r"\s+", " ", text)
    normalized = normalized.replace(",", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if not normalized:
        return None

    pause_patterns = (
        "pause runtime",
        "pause agents",
        "stop runtime",
        "stop agents",
        "/fund runtime pause",
        "/fund control pause",
    )
    resume_patterns = (
        "resume runtime",
        "resume agents",
        "start runtime",
        "start agents",
        "/fund runtime resume",
        "/fund control resume",
    )
    clear_patterns = (
        "clear halt",
        "clear system halt",
        "reset halt",
        "unhalt",
        "/fund halt clear",
        "/fund control clear-halt",
    )
    autopilot_patterns = (
        "kick autopilot",
        "autopilot now",
        "run autopilot now",
        "/fund autopilot kick",
        "/fund control kick-autopilot",
    )
    status_patterns = (
        "runtime status",
        "control status",
        "/fund runtime status",
        "/fund control status",
    )

    if any(phrase in normalized for phrase in pause_patterns):
        return {"action": "pause_runtime"}
    if any(phrase in normalized for phrase in resume_patterns):
        return {"action": "resume_runtime"}
    if any(phrase in normalized for phrase in clear_patterns):
        return {"action": "clear_halt"}
    if any(phrase in normalized for phrase in autopilot_patterns):
        return {"action": "kick_autopilot"}
    if any(phrase in normalized for phrase in status_patterns):
        return {"action": "runtime_status"}
    return None


class OpenClawCommandAdapter:
    """
    Maps OpenClaw channel messages into validated CEO commands for worker routing.
    """

    def __init__(
        self,
        *,
        runtime: FundAgentRuntime = fund_agent_runtime,
        token: str | None = None,
        enabled: bool | None = None,
        default_agent_id: str | None = None,
        channel_allowlist: Iterable[str] | None = None,
        sender_allowlist: Iterable[str] | None = None,
        role_allowlist: Iterable[str] | None = None,
        channel_role_policies: dict[str, set[str]] | None = None,
        fund_manager_mode: bool | None = None,
        fund_manager_agent_id: str | None = None,
        fund_manager_assigned_roles: Iterable[str] | None = None,
        max_text_length: int | None = None,
        log: AuditLog | None = None,
        clock: Callable[[], datetime] | None = None,
        event_sink: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        settings = get_settings()
        configured_fund_manager_mode = (
            settings.OPENCLAW_FUND_MANAGER_MODE if fund_manager_mode is None else bool(fund_manager_mode)
        )
        configured_token = token if token is not None else (
            os.getenv("OPENCLAW_COMMAND_TOKEN")
            or settings.OPENCLAW_COMMAND_TOKEN
            or os.getenv("OPENCLAW_INGEST_TOKEN")
            or settings.OPENCLAW_INGEST_TOKEN
        )
        configured_roles = (
            set(role_allowlist)
            if role_allowlist is not None
            else _parse_csv(settings.OPENCLAW_COMMAND_ROLE_ALLOWLIST)
        )
        if not configured_roles:
            configured_roles = set(ALLOWED_ROLES)
        configured_roles = {role for role in configured_roles if role in ALLOWED_ROLES}
        configured_roles.add("blog_writer")

        configured_channel_allowlist = (
            {item.strip().lower() for item in channel_allowlist if str(item).strip()}
            if channel_allowlist is not None
            else _parse_csv(settings.OPENCLAW_COMMAND_CHANNEL_ALLOWLIST)
        )
        configured_sender_allowlist = (
            {item.strip().lower() for item in sender_allowlist if str(item).strip()}
            if sender_allowlist is not None
            else _parse_csv(settings.OPENCLAW_COMMAND_SENDER_ALLOWLIST)
        )
        configured_channel_role_policies = (
            channel_role_policies
            if channel_role_policies is not None
            else _parse_channel_role_policies(settings.OPENCLAW_COMMAND_CHANNEL_ROLE_POLICIES, configured_roles)
        )
        configured_assigned_roles = (
            {str(item).strip().lower() for item in fund_manager_assigned_roles if str(item).strip()}
            if fund_manager_assigned_roles is not None
            else _parse_csv(settings.OPENCLAW_FUND_MANAGER_ASSIGNED_ROLES)
        )
        configured_assigned_roles = {role for role in configured_assigned_roles if role in ANALYST_ROLES}
        if not configured_assigned_roles:
            configured_assigned_roles = set(ANALYST_ROLES)
        if configured_fund_manager_mode:
            configured_roles.update(configured_assigned_roles)
            configured_roles.add("signal_swarm")
            configured_roles.add("fund_manager")

        self._runtime = runtime
        self._token = configured_token
        self._enabled = settings.OPENCLAW_COMMANDS_ENABLED if enabled is None else bool(enabled)
        self._default_agent_id = default_agent_id or settings.OPENCLAW_COMMAND_DEFAULT_AGENT_ID or "ceo"
        self._fund_manager_mode = configured_fund_manager_mode
        self._fund_manager_agent_id = str(
            fund_manager_agent_id or settings.OPENCLAW_FUND_MANAGER_AGENT_ID or "fund_manager"
        ).strip() or "fund_manager"
        self._fund_manager_assigned_roles = configured_assigned_roles
        self._channel_allowlist = configured_channel_allowlist
        self._sender_allowlist = configured_sender_allowlist
        self._role_allowlist = configured_roles
        self._channel_role_policies = {
            str(key).strip().lower(): {role for role in roles if role in self._role_allowlist}
            for key, roles in configured_channel_role_policies.items()
        }
        if "blog_writer" in self._role_allowlist:
            for key in list(self._channel_role_policies.keys()):
                self._channel_role_policies[key].add("blog_writer")
        if self._fund_manager_mode:
            for key in list(self._channel_role_policies.keys()):
                self._channel_role_policies[key].update(self._fund_manager_assigned_roles)
                self._channel_role_policies[key].add("signal_swarm")
                self._channel_role_policies[key].add("fund_manager")
        self._max_text_length = int(max_text_length or settings.OPENCLAW_COMMAND_MAX_TEXT_LENGTH or 4000)
        self._log = log or audit_log
        self._clock = clock or _utc_now
        self._event_sink = event_sink
        self._lock = RLock()
        self._seq = 0
        self._accepted: List[dict[str, Any]] = []
        self._rejected: List[dict[str, Any]] = []
        self._rejection_counts: Dict[str, int] = {}
        self._auth_failures = 0
        self._last_accepted_at: str | None = None
        self._last_rejected_at: str | None = None

    def route_message(self, message: dict[str, Any], token: str) -> dict[str, Any]:
        now = _to_iso(self._clock())
        if not self._enabled:
            return self._reject(reason="commands_disabled", message=message, occurred_at=now)
        if not self._is_authorized(token):
            return self._reject(reason="unauthorized", message=message, occurred_at=now, auth_failure=True)
        if not isinstance(message, dict):
            return self._reject(reason="invalid_payload_type", message={}, occurred_at=now)

        command = str(message.get("text") or message.get("command") or "").strip()
        if not command:
            return self._reject(reason="missing_command_text", message=message, occurred_at=now)
        if len(command) > self._max_text_length:
            return self._reject(reason="command_text_too_long", message=message, occurred_at=now)
        control = _parse_control_command(command)

        if data_integrity_guard.halted():
            action = str((control or {}).get("action") or "").strip().lower()
            if action not in {"clear_halt", "runtime_status"}:
                return self._reject(
                    reason=data_integrity_guard.halt_reason() or "system_halted",
                    message=message,
                    occurred_at=now,
                )

        channel_id = str(message.get("channel_id") or "").strip().lower()
        channel_name = str(message.get("channel_name") or "").strip().lower()
        sender_id = str(message.get("sender_id") or "").strip().lower()
        sender_name = str(message.get("sender_name") or "").strip().lower()

        if self._channel_allowlist:
            if channel_id not in self._channel_allowlist and channel_name not in self._channel_allowlist:
                return self._reject(reason="channel_not_allowed", message=message, occurred_at=now)
        if self._sender_allowlist:
            if sender_id not in self._sender_allowlist and sender_name not in self._sender_allowlist:
                return self._reject(reason="sender_not_allowed", message=message, occurred_at=now)

        if control is not None:
            channel_roles = self._allowed_roles_for_channel(channel_id, channel_name)
            if "fund_manager" not in channel_roles:
                return self._reject(reason="control_not_allowed_for_channel", message=message, occurred_at=now)
            run_id = str(message.get("run_id") or f"run-openclaw-control-{uuid4().hex[:12]}")
            agent_id = str(message.get("agent_id") or self._fund_manager_agent_id or self._default_agent_id)
            control_result = self._execute_control_action(
                action=str(control.get("action") or "").strip().lower(),
                run_id=run_id,
                agent_id=agent_id,
                reason=f"openclaw:{command[:120]}",
            )
            if not control_result.get("accepted", True):
                return self._reject(
                    reason=str(control_result.get("reason") or "control_action_rejected"),
                    message=message,
                    occurred_at=now,
                )
            with self._lock:
                self._seq += 1
                adapter_id = f"ocmd-{self._seq:08d}"
                record = {
                    "adapter_id": adapter_id,
                    "received_at": now,
                    "status": "accepted",
                    "role": "runtime_control",
                    "requested_role": "fund_manager",
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "message": message,
                    "route_result": control_result,
                    "control_action": control_result.get("action"),
                }
                self._accepted.append(record)
                self._last_accepted_at = now

            self._log.record(
                "openclaw.command.accepted",
                {
                    "adapter_id": adapter_id,
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "role": "runtime_control",
                    "requested_role": "fund_manager",
                    "command_id": control_result.get("control_id"),
                    "control_action": control_result.get("action"),
                    "channel_id": channel_id or None,
                    "channel_name": channel_name or None,
                    "sender_id": sender_id or None,
                    "sender_name": sender_name or None,
                },
            )
            self._emit_event(
                {
                    "event_id": adapter_id,
                    "event_type": "openclaw.command.accepted",
                    "received_at": now,
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "payload": record,
                }
            )
            return {
                "accepted": True,
                "adapter_id": adapter_id,
                "role": "runtime_control",
                "route_result": control_result,
            }

        explicit_role = message.get("target_role")
        requested_role = str(explicit_role).strip().lower() if explicit_role else _infer_role(command)
        if requested_role not in self._role_allowlist:
            return self._reject(reason="role_not_allowed", message=message, occurred_at=now)

        channel_roles = self._allowed_roles_for_channel(channel_id, channel_name)
        if requested_role not in channel_roles:
            return self._reject(reason="role_not_allowed_for_channel", message=message, occurred_at=now)

        run_id = str(message.get("run_id") or f"run-openclaw-{uuid4().hex[:12]}")
        requested_agent_id = str(message.get("agent_id") or self._default_agent_id)
        raw_priority = message.get("priority", 8)
        try:
            priority = max(0, min(10, int(raw_priority)))
        except Exception:
            priority = 8
        payload = dict(message.get("payload") or {})
        payload.setdefault("source_platform", str(message.get("platform") or "discord").strip().lower())
        payload.setdefault("source_channel_id", channel_id or None)
        payload.setdefault("source_channel_name", channel_name or None)
        payload.setdefault("source_sender_id", sender_id or None)
        payload.setdefault("source_sender_name", sender_name or None)
        payload.setdefault("source_message_id", str(message.get("message_id") or "").strip() or None)

        assigned_roles = self._resolve_assigned_roles(payload=payload)
        should_route_to_swarm = self._fund_manager_mode and (
            requested_role in {"fund_manager", "signal_swarm"} or requested_role in ANALYST_ROLES
        )
        if should_route_to_swarm:
            agent_id = str(message.get("agent_id") or self._fund_manager_agent_id)
            symbol = str(message.get("symbol") or payload.get("symbol") or _extract_symbol(command) or "SPY").upper().strip()
            swarm_payload = {
                **payload,
                "symbol": symbol,
                "signal_pack_roles": sorted(assigned_roles),
                "manager_agent_id": agent_id,
                "orchestration_mode": "openclaw_fund_manager",
            }
            route_result = self._runtime.enqueue_signal_swarm(
                run_id=run_id,
                symbol=symbol,
                agent_id=agent_id,
                command=command,
                payload=swarm_payload,
                priority=priority,
            )
            role = "signal_swarm"
        elif requested_role == "signal_swarm":
            agent_id = requested_agent_id
            symbol = str(message.get("symbol") or payload.get("symbol") or _extract_symbol(command) or "SPY").upper().strip()
            route_result = self._runtime.enqueue_signal_swarm(
                run_id=run_id,
                symbol=symbol,
                agent_id=agent_id,
                command=command,
                payload={**payload, "symbol": symbol, "signal_pack_roles": sorted(assigned_roles)},
                priority=priority,
            )
            role = "signal_swarm"
        else:
            agent_id = requested_agent_id
            route_result = self._runtime.enqueue_ceo_command(
                run_id=run_id,
                command=command,
                agent_id=agent_id,
                target_role=requested_role,
                payload=payload,
                priority=priority,
            )
            role = requested_role
        with self._lock:
            self._seq += 1
            adapter_id = f"ocmd-{self._seq:08d}"
            record = {
                "adapter_id": adapter_id,
                "received_at": now,
                "status": "accepted",
                "role": role,
                "requested_role": requested_role,
                "run_id": run_id,
                "agent_id": agent_id,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "message": message,
                "route_result": route_result,
            }
            self._accepted.append(record)
            self._last_accepted_at = now

        self._log.record(
            "openclaw.command.accepted",
            {
                "adapter_id": adapter_id,
                "run_id": run_id,
                "agent_id": agent_id,
                "role": role,
                "requested_role": requested_role,
                "task_id": route_result.get("task_id"),
                "task_ids": route_result.get("task_ids"),
                "command_id": route_result.get("command_id"),
                "signal_pack_id": route_result.get("signal_pack_id"),
                "fund_manager_mode": self._fund_manager_mode,
                "assigned_roles": sorted(assigned_roles),
                "channel_id": channel_id or None,
                "channel_name": channel_name or None,
                "sender_id": sender_id or None,
                "sender_name": sender_name or None,
            },
        )
        self._emit_event(
            {
                "event_id": adapter_id,
                "event_type": "openclaw.command.accepted",
                "received_at": now,
                "run_id": run_id,
                "agent_id": agent_id,
                "payload": record,
            }
        )
        return {
            "accepted": True,
            "adapter_id": adapter_id,
            "role": role,
            "route_result": route_result,
        }

    def health(self) -> dict[str, Any]:
        with self._lock:
            accepted_count = len(self._accepted)
            rejected_count = len(self._rejected)
            attempts = accepted_count + rejected_count
            return {
                "enabled": self._enabled,
                "auth_configured": bool(self._token),
                "total_attempts": attempts,
                "accepted_count": accepted_count,
                "rejected_count": rejected_count,
                "auth_failures": self._auth_failures,
                "last_accepted_at": self._last_accepted_at,
                "last_rejected_at": self._last_rejected_at,
                "rejection_reason_counts": dict(sorted(self._rejection_counts.items(), key=lambda kv: kv[0])),
                "channel_allowlist_size": len(self._channel_allowlist),
                "sender_allowlist_size": len(self._sender_allowlist),
                "role_allowlist": sorted(self._role_allowlist),
                "fund_manager_mode": self._fund_manager_mode,
                "fund_manager_agent_id": self._fund_manager_agent_id,
                "fund_manager_assigned_roles": sorted(self._fund_manager_assigned_roles),
                "data_integrity": data_integrity_guard.status(),
            }

    def list_rejected(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._rejected)
        return items[-limit:] if limit >= 0 else items

    def list_accepted(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._accepted)
        return items[-limit:] if limit >= 0 else items

    def set_event_sink(self, sink: Callable[[dict[str, Any]], Any] | None) -> None:
        self._event_sink = sink

    def _allowed_roles_for_channel(self, channel_id: str, channel_name: str) -> set[str]:
        for key in (channel_id, channel_name):
            if key and key in self._channel_role_policies:
                return self._channel_role_policies[key]
        return set(self._role_allowlist)

    def _execute_control_action(
        self,
        *,
        action: str,
        run_id: str,
        agent_id: str,
        reason: str,
    ) -> dict[str, Any]:
        control_id = f"ctrl-{uuid4().hex[:16]}"
        clean_action = str(action or "").strip().lower()
        clean_reason = str(reason or "openclaw_control").strip() or "openclaw_control"

        if clean_action == "runtime_status":
            runtime = self._runtime.status()
            result = {
                "accepted": True,
                "control_id": control_id,
                "action": "runtime_status",
                "status": "reported",
                "runtime_started": bool(runtime.get("started")),
                "halted": bool(data_integrity_guard.halted()),
                "halt_reason": data_integrity_guard.halt_reason(),
                "autopilot": runtime.get("autopilot", {}),
            }
            self._record_control_event(
                action="runtime_status",
                status="reported",
                reason=clean_reason,
                run_id=run_id,
                agent_id=agent_id,
                control_id=control_id,
                payload={"runtime_started": result["runtime_started"]},
            )
            return result

        if clean_action == "pause_runtime":
            was_started = bool(self._runtime.is_started())
            if was_started:
                self._schedule_runtime_coroutine(self._runtime.stop())
            status = "pausing" if was_started else "already_paused"
            self._record_control_event(
                action="pause_runtime",
                status=status,
                reason=clean_reason,
                run_id=run_id,
                agent_id=agent_id,
                control_id=control_id,
                payload={"runtime_started_before": was_started},
            )
            return {
                "accepted": True,
                "control_id": control_id,
                "action": "pause_runtime",
                "status": status,
                "runtime_started_before": was_started,
            }

        if clean_action == "resume_runtime":
            if data_integrity_guard.halted():
                halt_reason = data_integrity_guard.halt_reason() or "system_halted"
                self._record_control_event(
                    action="resume_runtime",
                    status="rejected",
                    reason=halt_reason,
                    run_id=run_id,
                    agent_id=agent_id,
                    control_id=control_id,
                    payload={"blocked": True},
                )
                return {"accepted": False, "reason": halt_reason, "control_id": control_id}
            was_started = bool(self._runtime.is_started())
            if not was_started:
                self._schedule_runtime_coroutine(self._runtime.start())
            status = "resuming" if not was_started else "already_running"
            self._record_control_event(
                action="resume_runtime",
                status=status,
                reason=clean_reason,
                run_id=run_id,
                agent_id=agent_id,
                control_id=control_id,
                payload={"runtime_started_before": was_started},
            )
            return {
                "accepted": True,
                "control_id": control_id,
                "action": "resume_runtime",
                "status": status,
                "runtime_started_before": was_started,
            }

        if clean_action == "clear_halt":
            cleared = data_integrity_guard.clear_halt(reason=clean_reason)
            self._record_control_event(
                action="clear_halt",
                status="halt_cleared",
                reason=clean_reason,
                run_id=run_id,
                agent_id=agent_id,
                control_id=control_id,
                payload={"previous_halt_reason": cleared.get("previous_halt_reason")},
            )
            return {
                "accepted": True,
                "control_id": control_id,
                "action": "clear_halt",
                "status": "halt_cleared",
                "clear_result": cleared,
            }

        if clean_action == "kick_autopilot":
            kicked = self._runtime.kick_autopilot(run_id=run_id)
            if not kicked.get("accepted"):
                reject_reason = str(kicked.get("reason") or "autopilot_rejected")
                self._record_control_event(
                    action="kick_autopilot",
                    status="rejected",
                    reason=reject_reason,
                    run_id=run_id,
                    agent_id=agent_id,
                    control_id=control_id,
                    payload={"accepted": False},
                )
                return {"accepted": False, "reason": reject_reason, "control_id": control_id}
            self._record_control_event(
                action="kick_autopilot",
                status="accepted",
                reason=clean_reason,
                run_id=run_id,
                agent_id=agent_id,
                control_id=control_id,
                payload={"accepted": True},
            )
            return {
                "accepted": True,
                "control_id": control_id,
                "action": "kick_autopilot",
                "status": "accepted",
                "result": kicked,
            }

        return {"accepted": False, "reason": "unknown_control_action", "control_id": control_id}

    def _schedule_runtime_coroutine(self, coro: Any) -> None:
        if not asyncio.iscoroutine(coro):
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
            return
        except RuntimeError:
            pass
        asyncio.run(coro)

    def _record_control_event(
        self,
        *,
        action: str,
        status: str,
        reason: str | None,
        run_id: str,
        agent_id: str,
        control_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event_payload = {
            "control_id": control_id,
            "action": str(action or "").strip().lower(),
            "status": str(status or "unknown").strip().lower(),
            "reason": str(reason or "").strip() or None,
            "actor": "openclaw.command_adapter",
            **dict(payload or {}),
        }
        self._log.record(
            "runtime.control",
            {
                "run_id": run_id,
                "agent_id": agent_id,
                **event_payload,
            },
        )
        knowledge_graph.ingest(
            source="runtime",
            event_type=f"runtime.control.{event_payload['action']}",
            run_id=run_id,
            agent_id=agent_id,
            payload=event_payload,
            source_event_id=control_id,
        )

    def _resolve_assigned_roles(self, *, payload: dict[str, Any]) -> set[str]:
        raw = payload.get("assigned_roles")
        requested: set[str] = set()
        if isinstance(raw, str):
            requested = {item.strip().lower() for item in raw.split(",") if item.strip()}
        elif isinstance(raw, (list, tuple, set)):
            requested = {str(item).strip().lower() for item in raw if str(item).strip()}
        candidate = requested or set(self._fund_manager_assigned_roles)
        candidate = {role for role in candidate if role in ANALYST_ROLES}
        return candidate or set(self._fund_manager_assigned_roles)

    def _is_authorized(self, token: str) -> bool:
        return bool(self._token) and bool(token) and secrets.compare_digest(str(token), self._token)

    def _reject(
        self,
        *,
        reason: str,
        message: dict[str, Any],
        occurred_at: str,
        auth_failure: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            reject_id = f"ocmd-rej-{self._seq:08d}"
            record = {
                "reject_id": reject_id,
                "received_at": occurred_at,
                "status": "rejected",
                "reason": reason,
                "message": message,
            }
            self._rejected.append(record)
            self._last_rejected_at = occurred_at
            self._rejection_counts[reason] = self._rejection_counts.get(reason, 0) + 1
            if auth_failure:
                self._auth_failures += 1

        self._log.record(
            "openclaw.command.rejected",
            {
                "reject_id": reject_id,
                "reason": reason,
                "run_id": message.get("run_id") if isinstance(message, dict) else None,
                "agent_id": message.get("agent_id") if isinstance(message, dict) else None,
                "channel_id": message.get("channel_id") if isinstance(message, dict) else None,
                "channel_name": message.get("channel_name") if isinstance(message, dict) else None,
                "sender_id": message.get("sender_id") if isinstance(message, dict) else None,
            },
        )
        self._emit_event(
            {
                "event_id": reject_id,
                "event_type": "openclaw.command.rejected",
                "received_at": occurred_at,
                "run_id": message.get("run_id") if isinstance(message, dict) else None,
                "agent_id": message.get("agent_id") if isinstance(message, dict) else None,
                "payload": record,
            }
        )
        return {"accepted": False, "reason": reason}

    def _emit_event(self, event: dict[str, Any]) -> None:
        if self._event_sink is None:
            return
        try:
            self._event_sink(dict(event))
        except Exception:
            pass


openclaw_command_adapter = OpenClawCommandAdapter()
