from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from threading import RLock
from typing import Any, Iterable, Literal
from uuid import uuid4

from app.config import get_settings
from app.fund.ai_role_adapter import ai_role_adapter
from app.fund.contracts import (
    ProvenanceRef,
    ResearchReport as ContractResearchReport,
    SentimentSnapshot as ContractSentimentSnapshot,
    Sleeve,
)
from app.fund.blog_service import blog_service
from app.fund.ingestion_adapters import market_ingestion
from app.fund.market_session import market_session_status
from app.fund.orchestrator import FirmOrchestrator, firm_orchestrator
from app.fund.runtime_guard import data_integrity_guard
from app.fund.task_bus import TaskBus, task_bus
from app.fund.agent_hierarchy import agent_hierarchy
from app.websocket.agent_events import publish_agent_event


AnalystRole = Literal[
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_timeseries_analyst",
    "insight_researcher",
    "hedge_fund_researcher",
]
WorkerRole = Literal[
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_timeseries_analyst",
    "insight_researcher",
    "hedge_fund_researcher",
    "fund_manager",
    "trader",
    "risk_auditor",
    "blog_writer",
]

ANALYST_ROLES: tuple[AnalystRole, ...] = (
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_timeseries_analyst",
    "insight_researcher",
    "hedge_fund_researcher",
)
WORKER_ROLES: tuple[WorkerRole, ...] = (*ANALYST_ROLES, "fund_manager", "trader", "risk_auditor", "blog_writer")
ROLE_ALIASES: dict[str, WorkerRole] = {
    "researcher": "insight_researcher",
    "sentiment_researcher": "sentiment_analyst",
    "blog_agent": "blog_writer",
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_decimal(value: Any, fallback: str = "0.5") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(fallback)


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _parse_symbol_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return tuple()
    out: list[str] = []
    seen: set[str] = set()
    for raw in value.split(","):
        symbol = raw.strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        out.append(symbol)
    return tuple(out)


def _normalize_role(value: str | None) -> WorkerRole:
    normalized = str(value or "").strip().lower()
    if normalized in ROLE_ALIASES:
        return ROLE_ALIASES[normalized]
    if normalized in WORKER_ROLES:
        return normalized  # type: ignore[return-value]
    return "fund_manager"


def _normalize_sleeve(value: str | None) -> Sleeve:
    try:
        return Sleeve(str(value or "tactical").strip().lower())
    except Exception:
        return Sleeve.TACTICAL


def _extract_symbol(text: str, fallback: str = "SPY") -> str:
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
    }
    for token in tokens:
        if token not in ignored:
            return token
    return fallback


def _extract_metric(findings: Iterable[str], label: str) -> float | None:
    pattern = re.compile(rf"{re.escape(label)}\s*:?\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
    for row in findings:
        text = str(row or "").strip()
        match = pattern.search(text)
        if not match:
            continue
        try:
            return float(match.group(1))
        except Exception:
            return None
    return None


def _infer_role_from_command(command: str) -> WorkerRole:
    text = command.lower()
    if any(key in text for key in ("blog", "post", "publish article", "write article", "newsletter")):
        return "blog_writer"
    if any(key in text for key in ("technical", "rsi", "macd", "ema", "atr")):
        return "technical_analyst"
    if any(key in text for key in ("fundamental", "valuation", "earnings", "fmp")):
        return "fundamental_analyst"
    if any(key in text for key in ("sentiment", "news", "x ", "twitter", "social")):
        return "sentiment_analyst"
    if any(key in text for key in ("ml", "timeseries", "forecast", "model")):
        return "ml_timeseries_analyst"
    if any(key in text for key in ("insight", "narrative", "research", "investigate", "analyze")):
        return "insight_researcher"
    if any(key in text for key in ("macro", "scenario", "hedge fund")):
        return "hedge_fund_researcher"
    if any(key in text for key in ("risk", "audit", "compliance")):
        return "risk_auditor"
    if any(key in text for key in ("trade", "execute", "entry", "exit")):
        return "trader"
    return "insight_researcher"


@dataclass
class WorkerState:
    role: WorkerRole
    started: bool = False
    running: bool = False
    last_heartbeat_at: str | None = None
    last_task_id: str | None = None
    last_task_status: str | None = None
    last_error: str | None = None
    completed_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "started": self.started,
            "running": self.running,
            "last_heartbeat_at": self.last_heartbeat_at,
            "last_task_id": self.last_task_id,
            "last_task_status": self.last_task_status,
            "last_error": self.last_error,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "blocked_count": self.blocked_count,
        }


@dataclass
class SignalPackState:
    signal_pack_id: str
    run_id: str
    symbol: str
    expected_roles: set[str]
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    dispatched: bool = False
    composite_report_id: str | None = None
    fund_manager_task_id: str | None = None


class FundAgentRuntime:
    def __init__(
        self,
        *,
        orchestrator: FirmOrchestrator = firm_orchestrator,
        task_bus_service: TaskBus = task_bus,
        enabled: bool = True,
        poll_interval_seconds: float = 1.5,
        roles: Iterable[WorkerRole] = WORKER_ROLES,
        autopilot_enabled: bool = False,
        autopilot_interval_seconds: float = 120.0,
        autopilot_symbols: Iterable[str] | None = None,
        autopilot_dynamic_universe_enabled: bool = True,
        autopilot_scout_symbols: Iterable[str] | None = None,
        autopilot_scout_max_symbols: int = 4,
        autopilot_default_side: Literal["buy", "sell"] = "buy",
        autopilot_default_quantity: float = 1.0,
        autopilot_sleeve: Sleeve = Sleeve.TACTICAL,
        session_guard_enabled: bool = True,
        block_trades_when_closed: bool = True,
        min_trade_conviction: float = 0.60,
        allow_cash_hold: bool = True,
        blog_editorial_enabled: bool = True,
        blog_editorial_interval_hours: int = 12,
        blog_editorial_target_per_day: int = 2,
        blog_editorial_min_confidence: float = 0.55,
    ) -> None:
        self._orchestrator = orchestrator
        self._task_bus = task_bus_service
        self._enabled = bool(enabled)
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._roles = tuple(roles)
        self._worker_tasks: dict[WorkerRole, asyncio.Task] = {}
        self._autopilot_task: asyncio.Task | None = None
        self._state_lock = RLock()
        self._signal_pack_lock = RLock()
        self._states = {role: WorkerState(role=role) for role in self._roles}
        self._signal_packs: dict[str, SignalPackState] = {}
        self._started = False

        symbols = tuple(str(item).strip().upper() for item in (autopilot_symbols or ()) if str(item).strip())
        scout_symbols = tuple(str(item).strip().upper() for item in (autopilot_scout_symbols or ()) if str(item).strip())
        self._autopilot_enabled = bool(autopilot_enabled)
        self._autopilot_interval_seconds = max(5.0, float(autopilot_interval_seconds))
        self._autopilot_symbols = tuple(dict.fromkeys(symbols)) or ("SPY",)
        self._autopilot_dynamic_universe_enabled = bool(autopilot_dynamic_universe_enabled)
        merged_scout_universe = tuple(dict.fromkeys((*self._autopilot_symbols, *scout_symbols)))
        self._autopilot_scout_symbols = merged_scout_universe or self._autopilot_symbols
        self._autopilot_scout_max_symbols = max(1, int(autopilot_scout_max_symbols))
        self._autopilot_default_side: Literal["buy", "sell"] = "sell" if autopilot_default_side == "sell" else "buy"
        self._autopilot_default_quantity = max(0.01, float(autopilot_default_quantity))
        self._autopilot_sleeve = autopilot_sleeve
        self._session_guard_enabled = bool(session_guard_enabled)
        self._block_trades_when_closed = bool(block_trades_when_closed)
        self._min_trade_conviction = max(0.0, min(1.0, float(min_trade_conviction)))
        self._allow_cash_hold = bool(allow_cash_hold)
        self._autopilot_cycles = 0
        self._autopilot_enqueued = 0
        self._autopilot_last_run_id: str | None = None
        self._autopilot_last_run_at: str | None = None
        self._autopilot_last_error: str | None = None
        self._autopilot_last_session: dict[str, Any] | None = None
        self._autopilot_last_scout: dict[str, Any] | None = None
        self._last_halt_drain_reason: str | None = None
        self._blog_editorial_enabled = bool(blog_editorial_enabled)
        self._blog_editorial_interval_seconds = max(60.0, float(max(1, int(blog_editorial_interval_hours)) * 3600))
        self._blog_editorial_target_per_day = max(0, int(blog_editorial_target_per_day))
        self._blog_editorial_min_confidence = max(0.0, min(1.0, float(blog_editorial_min_confidence)))
        self._blog_editorial_task: asyncio.Task | None = None
        self._blog_editorial_cycles = 0
        self._blog_editorial_enqueued = 0
        self._blog_editorial_last_run_id: str | None = None
        self._blog_editorial_last_run_at: str | None = None
        self._blog_editorial_last_error: str | None = None

    async def start(self) -> None:
        if not self._enabled or self._started:
            return
        self._started = True
        
        # Initialize agent hierarchy statuses
        for role in self._roles:
            agent_id = f"agent-{role}"
            agent_hierarchy.update_agent_status(
                agent_id=agent_id,
                role=role,
                status="idle",
            )
            publish_agent_event("agent.status_changed", {
                "agent_id": agent_id,
                "role": role,
                "status": "idle",
            })
        
        for role in self._roles:
            self._states[role].started = True
            self._worker_tasks[role] = asyncio.create_task(self._worker_loop(role), name=f"fund-worker:{role}")
        if self._autopilot_enabled:
            self._autopilot_task = asyncio.create_task(self._autopilot_loop(), name="fund-autopilot")
        if self._blog_editorial_enabled and self._blog_editorial_target_per_day > 0:
            self._blog_editorial_task = asyncio.create_task(self._blog_editorial_loop(), name="fund-blog-editorial")

    async def stop(self) -> None:
        tasks = list(self._worker_tasks.values())
        self._worker_tasks.clear()
        self._started = False
        if self._autopilot_task is not None:
            tasks.append(self._autopilot_task)
            self._autopilot_task = None
        if self._blog_editorial_task is not None:
            tasks.append(self._blog_editorial_task)
            self._blog_editorial_task = None
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        with self._state_lock:
            for role in self._roles:
                self._states[role].running = False

    def is_started(self) -> bool:
        return self._started

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            workers = [self._states[role].to_dict() for role in self._roles]
            autopilot = {
                "enabled": self._autopilot_enabled,
                "running": self._autopilot_task is not None and not self._autopilot_task.done(),
                "interval_seconds": self._autopilot_interval_seconds,
                "symbols": list(self._autopilot_symbols),
                "dynamic_universe_enabled": self._autopilot_dynamic_universe_enabled,
                "scout_symbols": list(self._autopilot_scout_symbols),
                "scout_max_symbols": self._autopilot_scout_max_symbols,
                "default_side": self._autopilot_default_side,
                "default_quantity": self._autopilot_default_quantity,
                "sleeve": self._autopilot_sleeve.value,
                "session_guard_enabled": self._session_guard_enabled,
                "block_trades_when_closed": self._block_trades_when_closed,
                "min_trade_conviction": self._min_trade_conviction,
                "allow_cash_hold": self._allow_cash_hold,
                "cycles": self._autopilot_cycles,
                "enqueued_count": self._autopilot_enqueued,
                "last_run_id": self._autopilot_last_run_id,
                "last_run_at": self._autopilot_last_run_at,
                "last_error": self._autopilot_last_error,
                "last_session": dict(self._autopilot_last_session or {}),
                "last_scout": dict(self._autopilot_last_scout or {}),
            }
            blog_editorial = {
                "enabled": self._blog_editorial_enabled,
                "running": self._blog_editorial_task is not None and not self._blog_editorial_task.done(),
                "interval_seconds": self._blog_editorial_interval_seconds,
                "target_per_day": self._blog_editorial_target_per_day,
                "min_confidence": self._blog_editorial_min_confidence,
                "cycles": self._blog_editorial_cycles,
                "enqueued_count": self._blog_editorial_enqueued,
                "last_run_id": self._blog_editorial_last_run_id,
                "last_run_at": self._blog_editorial_last_run_at,
                "last_error": self._blog_editorial_last_error,
            }
            halt_guard = {
                "halted": data_integrity_guard.halted(),
                "reason": data_integrity_guard.halt_reason(),
                "last_queue_drain_reason": self._last_halt_drain_reason,
            }
        with self._signal_pack_lock:
            packs = [
                {
                    "signal_pack_id": state.signal_pack_id,
                    "run_id": state.run_id,
                    "symbol": state.symbol,
                    "expected_roles": sorted(state.expected_roles),
                    "completed_roles": sorted(state.outputs.keys()),
                    "dispatched": state.dispatched,
                    "composite_report_id": state.composite_report_id,
                    "fund_manager_task_id": state.fund_manager_task_id,
                }
                for state in self._signal_packs.values()
            ]
        return {
            "enabled": self._enabled,
            "started": self._started,
            "poll_interval_seconds": self._poll_interval_seconds,
            "workers": workers,
            "autopilot": autopilot,
            "signal_packs": packs,
            "ai_role_adapter": ai_role_adapter.health(),
            "data_integrity": data_integrity_guard.status(),
            "halt_guard": halt_guard,
            "blog_editorial": blog_editorial,
        }

    def enqueue_ceo_command(
        self,
        *,
        run_id: str,
        command: str,
        agent_id: str = "ceo",
        target_role: str | None = None,
        payload: dict[str, Any] | None = None,
        priority: int = 8,
    ) -> dict[str, Any]:
        if data_integrity_guard.halted():
            return {
                "command_id": f"ceocmd-{uuid4().hex}",
                "run_id": run_id,
                "status": "blocked",
                "reason": data_integrity_guard.halt_reason() or "system_halted",
            }
        clean_payload = dict(payload or {})
        if clean_payload.get("orchestrate_swarm") is True:
            symbol = str(clean_payload.get("symbol") or _extract_symbol(command)).upper()
            return self.enqueue_signal_swarm(
                run_id=run_id,
                symbol=symbol,
                agent_id=agent_id,
                command=command,
                payload=clean_payload,
                priority=priority,
            )

        role = _normalize_role(target_role) if target_role else _infer_role_from_command(command)
        command_id = f"ceocmd-{uuid4().hex}"
        task = self._task_bus.create_task(
            run_id=run_id,
            agent_id=agent_id,
            role=role,
            priority=max(0, min(10, int(priority))),
            payload={"command_id": command_id, "command": command, **clean_payload},
        )
        return {"command_id": command_id, "task_id": task.task_id, "role": role, "run_id": run_id, "status": task.status}

    def enqueue_signal_swarm(
        self,
        *,
        run_id: str,
        symbol: str,
        agent_id: str = "ceo",
        command: str = "swarm",
        payload: dict[str, Any] | None = None,
        priority: int = 8,
    ) -> dict[str, Any]:
        if data_integrity_guard.halted():
            return {
                "command_id": f"swarm-{uuid4().hex}",
                "run_id": run_id,
                "status": "blocked",
                "reason": data_integrity_guard.halt_reason() or "system_halted",
            }
        clean_payload = dict(payload or {})
        clean_symbol = str(symbol or clean_payload.get("symbol") or "SPY").upper().strip()
        signal_pack_id = f"sigpack-{uuid4().hex[:16]}"
        expected_roles = set(str(role) for role in clean_payload.get("signal_pack_roles") or ANALYST_ROLES)
        expected_roles = {role for role in expected_roles if role in ANALYST_ROLES}
        if not expected_roles:
            expected_roles = set(ANALYST_ROLES)

        queued_tasks: list[str] = []
        for role in expected_roles:
            task = self._task_bus.create_task(
                run_id=run_id,
                agent_id=agent_id,
                role=role,
                priority=max(0, min(10, int(priority))),
                payload={
                    "command": command,
                    "symbol": clean_symbol,
                    "side": str(clean_payload.get("side") or self._autopilot_default_side),
                    "quantity": float(clean_payload.get("quantity") or self._autopilot_default_quantity),
                    "price": clean_payload.get("price"),
                    "sleeve": str(clean_payload.get("sleeve") or self._autopilot_sleeve.value),
                    "conviction": float(clean_payload.get("conviction") or 0.7),
                    "signal_pack_id": signal_pack_id,
                    "signal_pack_roles": sorted(expected_roles),
                    "metadata": {**dict(clean_payload.get("metadata") or {}), "swarm": True},
                },
            )
            queued_tasks.append(task.task_id)

        with self._signal_pack_lock:
            self._signal_packs[signal_pack_id] = SignalPackState(
                signal_pack_id=signal_pack_id,
                run_id=run_id,
                symbol=clean_symbol,
                expected_roles=set(expected_roles),
            )

        return {
            "command_id": f"swarm-{uuid4().hex}",
            "signal_pack_id": signal_pack_id,
            "role": "signal_swarm",
            "run_id": run_id,
            "symbol": clean_symbol,
            "task_ids": queued_tasks,
            "status": "queued",
        }

    def kick_autopilot(self, run_id: str | None = None) -> dict[str, Any]:
        if not self._started:
            return {"accepted": False, "reason": "runtime_not_started"}
        if data_integrity_guard.halted():
            return {"accepted": False, "reason": data_integrity_guard.halt_reason() or "system_halted"}
        cycle_run_id = run_id or f"run-autopilot-{uuid4().hex[:12]}"
        result = self._enqueue_autopilot_cycle(cycle_run_id)
        result["accepted"] = True
        result["manual"] = True
        return result

    async def _worker_loop(self, role: WorkerRole) -> None:
        while True:
            with self._state_lock:
                state = self._states[role]
                state.running = True
                state.last_heartbeat_at = _utc_iso()
                
                # Publish agent status to hierarchy
                agent_id = f"agent-{role}"
                agent_hierarchy.update_agent_status(
                    agent_id=agent_id,
                    role=role,
                    status="running",
                    last_task_id=state.last_task_id,
                    task_count=state.completed_count + state.failed_count + state.blocked_count,
                    success_count=state.completed_count,
                    failed_count=state.failed_count,
                    blocked_count=state.blocked_count,
                )
                
                # Publish to WebSocket
                publish_agent_event("agent.status_changed", {
                    "agent_id": agent_id,
                    "role": role,
                    "status": "running",
                    "last_heartbeat": state.last_heartbeat_at,
                    "task_count": state.completed_count + state.failed_count + state.blocked_count,
                })
                
            if data_integrity_guard.halted():
                halt_reason = data_integrity_guard.halt_reason() or "system_halted"
                with self._state_lock:
                    if self._last_halt_drain_reason != halt_reason:
                        self._task_bus.block_queued(
                            reason=halt_reason,
                            roles=[str(item) for item in self._roles],
                            extra_details={"halted": True, "blocked_by": "runtime_guard"},
                        )
                        self._last_halt_drain_reason = halt_reason
                with self._state_lock:
                    state = self._states[role]
                    state.running = False
                    state.last_error = halt_reason
                    state.last_task_status = "blocked"
                    
                    # Publish halted status
                    agent_id = f"agent-{role}"
                    agent_hierarchy.update_agent_status(
                        agent_id=agent_id,
                        role=role,
                        status="idle",
                        last_error=halt_reason,
                        task_count=state.completed_count + state.failed_count + state.blocked_count,
                        success_count=state.completed_count,
                        failed_count=state.failed_count,
                        blocked_count=state.blocked_count,
                    )
                    
                    publish_agent_event("agent.status_changed", {
                        "agent_id": agent_id,
                        "role": role,
                        "status": "idle",
                        "last_error": halt_reason,
                    })
                await asyncio.sleep(max(self._poll_interval_seconds, 2.0))
                continue
            with self._state_lock:
                self._last_halt_drain_reason = None
            task = self._task_bus.claim_next_queued(role)
            if task is None:
                await asyncio.sleep(self._poll_interval_seconds)
                continue

            with self._state_lock:
                state = self._states[role]
                state.last_task_id = task.task_id
                state.last_task_status = "running"
                state.last_error = None
                
                # Publish task started
                agent_id = f"agent-{role}"
                agent_hierarchy.update_agent_status(
                    agent_id=agent_id,
                    role=role,
                    status="running",
                    current_task=task.task_id,
                    task_count=state.completed_count + state.failed_count + state.blocked_count,
                    success_count=state.completed_count,
                    failed_count=state.failed_count,
                    blocked_count=state.blocked_count,
                )
                
                publish_agent_event("agent.task_started", {
                    "agent_id": agent_id,
                    "role": role,
                    "task_id": task.task_id,
                    "run_id": task.run_id,
                    "status": "running",
                })

            try:
                result = await self._process_task(role, task.payload, run_id=task.run_id, task_id=task.task_id)
                status = str(result.get("status", "completed"))
                if status == "blocked":
                    self._task_bus.set_status(task.task_id, "blocked", result)
                    with self._state_lock:
                        state = self._states[role]
                        state.blocked_count += 1
                        state.last_task_status = "blocked"
                        
                        # Publish task blocked
                        agent_id = f"agent-{role}"
                        agent_hierarchy.update_agent_status(
                            agent_id=agent_id,
                            role=role,
                            status="idle",
                            last_task_id=task.task_id,
                            last_task_status="blocked",
                            task_count=state.completed_count + state.failed_count + state.blocked_count,
                            success_count=state.completed_count,
                            failed_count=state.failed_count,
                            blocked_count=state.blocked_count,
                        )
                        
                        publish_agent_event("agent.task_completed", {
                            "agent_id": agent_id,
                            "role": role,
                            "task_id": task.task_id,
                            "status": "blocked",
                        })
                else:
                    self._task_bus.set_status(task.task_id, "completed", result)
                    with self._state_lock:
                        state = self._states[role]
                        state.completed_count += 1
                        state.last_task_status = "completed"
                        
                        # Publish task completed
                        agent_id = f"agent-{role}"
                        agent_hierarchy.update_agent_status(
                            agent_id=agent_id,
                            role=role,
                            status="idle",
                            last_task_id=task.task_id,
                            last_task_status="completed",
                            task_count=state.completed_count + state.failed_count + state.blocked_count,
                            success_count=state.completed_count,
                            failed_count=state.failed_count,
                            blocked_count=state.blocked_count,
                        )
                        
                        publish_agent_event("agent.task_completed", {
                            "agent_id": agent_id,
                            "role": role,
                            "task_id": task.task_id,
                            "status": "completed",
                        })
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._task_bus.set_status(task.task_id, "failed", {"error": str(exc)})
                with self._state_lock:
                    state = self._states[role]
                    state.failed_count += 1
                    state.last_task_status = "failed"
                    state.last_error = str(exc)
                    
                    # Publish task failed
                    agent_id = f"agent-{role}"
                    agent_hierarchy.update_agent_status(
                        agent_id=agent_id,
                        role=role,
                        status="error",
                        last_task_id=task.task_id,
                        last_task_status="failed",
                        last_error=str(exc),
                        task_count=state.completed_count + state.failed_count + state.blocked_count,
                        success_count=state.completed_count,
                        failed_count=state.failed_count,
                        blocked_count=state.blocked_count,
                    )
                    
                    publish_agent_event("agent.error", {
                        "agent_id": agent_id,
                        "role": role,
                        "task_id": task.task_id,
                        "error": str(exc),
                        "status": "failed",
                    })
            finally:
                with self._state_lock:
                    self._states[role].last_heartbeat_at = _utc_iso()

    async def _autopilot_loop(self) -> None:
        while True:
            try:
                if data_integrity_guard.halted():
                    with self._state_lock:
                        self._autopilot_last_error = data_integrity_guard.halt_reason() or "system_halted"
                        self._autopilot_last_run_at = _utc_iso()
                    await asyncio.sleep(self._autopilot_interval_seconds)
                    continue
                cycle_run_id = f"run-autopilot-{uuid4().hex[:12]}"
                self._enqueue_autopilot_cycle(cycle_run_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self._state_lock:
                    self._autopilot_last_error = str(exc)
                    self._autopilot_last_run_at = _utc_iso()
            await asyncio.sleep(self._autopilot_interval_seconds)

    async def _blog_editorial_loop(self) -> None:
        while True:
            try:
                if data_integrity_guard.halted():
                    with self._state_lock:
                        self._blog_editorial_last_error = data_integrity_guard.halt_reason() or "system_halted"
                        self._blog_editorial_last_run_at = _utc_iso()
                    await asyncio.sleep(self._blog_editorial_interval_seconds)
                    continue

                cycle_run_id = f"run-blog-editorial-{uuid4().hex[:10]}"
                self._enqueue_blog_editorial_cycle(cycle_run_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self._state_lock:
                    self._blog_editorial_last_error = str(exc)
                    self._blog_editorial_last_run_at = _utc_iso()
            await asyncio.sleep(self._blog_editorial_interval_seconds)

    def _enqueue_autopilot_cycle(self, run_id: str) -> dict[str, Any]:
        session = self._market_session()
        if self._session_guard_enabled and (not session.get("open") or not session.get("trading_day")):
            reason = str(session.get("reason") or "market_closed")
            with self._state_lock:
                self._autopilot_cycles += 1
                self._autopilot_last_run_id = run_id
                self._autopilot_last_run_at = _utc_iso()
                self._autopilot_last_error = reason
                self._autopilot_last_session = dict(session)
                self._autopilot_last_scout = {
                    "selected_symbols": [],
                    "candidate_count": len(self._autopilot_scout_symbols),
                    "dynamic_universe_enabled": self._autopilot_dynamic_universe_enabled,
                    "reason": reason,
                }
            return {"run_id": run_id, "enqueued_count": 0, "task_ids": [], "reason": reason, "session": session}

        selected_symbols, scout_meta = self._resolve_autopilot_symbols()
        queued_ids: list[str] = []
        for symbol in selected_symbols:
            if self._has_inflight_analyst_tasks(symbol=symbol):
                continue
            swarm = self.enqueue_signal_swarm(
                run_id=run_id,
                symbol=symbol,
                agent_id="autopilot_coordinator",
                command=f"autopilot swarm {symbol}",
                payload={
                    "side": self._autopilot_default_side,
                    "quantity": self._autopilot_default_quantity,
                    "sleeve": self._autopilot_sleeve.value,
                    "metadata": {"autopilot": True},
                },
                priority=7,
            )
            queued_ids.extend(list(swarm.get("task_ids") or []))

        with self._state_lock:
            self._autopilot_cycles += 1
            self._autopilot_enqueued += len(queued_ids)
            self._autopilot_last_run_id = run_id
            self._autopilot_last_run_at = _utc_iso()
            self._autopilot_last_error = None
            self._autopilot_last_session = dict(session)
            self._autopilot_last_scout = dict(scout_meta)

        return {
            "run_id": run_id,
            "enqueued_count": len(queued_ids),
            "task_ids": queued_ids,
            "symbol_count": len(selected_symbols),
            "selected_symbols": list(selected_symbols),
            "session": session,
            "scout": scout_meta,
        }

    def _market_session(self) -> dict[str, Any]:
        return market_session_status(get_settings())

    def _resolve_autopilot_symbols(self) -> tuple[tuple[str, ...], dict[str, Any]]:
        if not self._autopilot_dynamic_universe_enabled:
            selected = tuple(self._autopilot_symbols[: self._autopilot_scout_max_symbols])
            return selected, {
                "dynamic_universe_enabled": False,
                "candidate_count": len(self._autopilot_symbols),
                "selected_symbols": list(selected),
            }

        scored: list[tuple[float, str]] = []
        for symbol in self._autopilot_scout_symbols:
            score = self._score_autopilot_symbol(symbol)
            if score is None:
                continue
            scored.append((score, symbol))

        if not scored:
            fallback = tuple(self._autopilot_symbols[: self._autopilot_scout_max_symbols])
            return fallback, {
                "dynamic_universe_enabled": True,
                "candidate_count": len(self._autopilot_scout_symbols),
                "selected_symbols": list(fallback),
                "reason": "scout_no_scores_fallback_to_seed",
            }

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = tuple(symbol for _, symbol in scored[: self._autopilot_scout_max_symbols])
        return selected, {
            "dynamic_universe_enabled": True,
            "candidate_count": len(self._autopilot_scout_symbols),
            "selected_symbols": list(selected),
            "top_scores": [{"symbol": symbol, "score": round(score, 4)} for score, symbol in scored[:5]],
        }

    def _score_autopilot_symbol(self, symbol: str) -> float | None:
        normalized = str(symbol or "").upper().strip()
        if not normalized:
            return None
        try:
            technical = market_ingestion.build_technical_report(normalized)
            ml = market_ingestion.build_ml_timeseries_report(normalized)
            sentiment = market_ingestion.build_sentiment(normalized)
        except Exception:
            return None

        ml_prob_up = _extract_metric(ml.findings, "Directional probability(up)")
        if ml_prob_up is None:
            ml_prob_up = 0.5
        ml_prob_up = max(0.0, min(1.0, float(ml_prob_up)))
        sentiment_norm = max(0.0, min(1.0, (_to_float(sentiment.sentiment_score, 0.0) + 1.0) / 2.0))
        tech_conf = max(0.0, min(1.0, _to_float(technical.confidence, 0.5)))
        ml_conf = max(0.0, min(1.0, _to_float(ml.confidence, 0.5)))
        return (ml_prob_up * 0.55) + (sentiment_norm * 0.15) + (tech_conf * 0.15) + (ml_conf * 0.15)

    def _enqueue_blog_editorial_cycle(self, run_id: str) -> dict[str, Any]:
        remaining = blog_service.daily_quota_remaining(self._blog_editorial_target_per_day)
        if remaining <= 0:
            with self._state_lock:
                self._blog_editorial_cycles += 1
                self._blog_editorial_last_run_id = run_id
                self._blog_editorial_last_run_at = _utc_iso()
                self._blog_editorial_last_error = None
            return {"run_id": run_id, "enqueued_count": 0, "reason": "daily_quota_reached"}

        reports = self._orchestrator.list_recent_research_reports(limit=200)
        candidates = blog_service.select_editorial_candidates(
            reports=reports,
            min_confidence=self._blog_editorial_min_confidence,
            limit=remaining,
        )

        queued_task_ids: list[str] = []
        for report in candidates:
            report_id = str(report.get("report_id") or "").strip()
            if not report_id:
                continue
            symbol = str((report.get("asset_universe") or ["MARKET"])[0]).upper().strip()
            confidence = float(report.get("confidence") or 0.0)
            task = self._task_bus.create_task(
                run_id=run_id,
                agent_id="editorial_coordinator",
                role="blog_writer",
                priority=8,
                payload={
                    "report_ids": [report_id],
                    "symbol": symbol,
                    "command": (
                        f"Write a specific AI-fintech-hedge-fund editorial for {symbol} "
                        f"(source confidence={confidence:.2f}). Include scenario map, risk controls, and concrete monitoring checklist."
                    ),
                    "trigger_source": "scheduled_editorial",
                    "metadata": {
                        "scheduled": True,
                        "confidence": confidence,
                        "target_per_day": self._blog_editorial_target_per_day,
                    },
                },
            )
            queued_task_ids.append(task.task_id)

        with self._state_lock:
            self._blog_editorial_cycles += 1
            self._blog_editorial_enqueued += len(queued_task_ids)
            self._blog_editorial_last_run_id = run_id
            self._blog_editorial_last_run_at = _utc_iso()
            self._blog_editorial_last_error = None

        return {
            "run_id": run_id,
            "enqueued_count": len(queued_task_ids),
            "task_ids": queued_task_ids,
            "candidate_count": len(candidates),
            "remaining_quota": max(0, remaining - len(queued_task_ids)),
        }

    def _has_inflight_analyst_tasks(self, *, symbol: str) -> bool:
        normalized_symbol = str(symbol).upper().strip()
        for task in self._task_bus.list_tasks():
            if task.role not in ANALYST_ROLES:
                continue
            if task.status not in {"queued", "running"}:
                continue
            task_symbol = str(task.payload.get("symbol") or task.payload.get("asset") or "").upper().strip()
            if task_symbol == normalized_symbol:
                return True
        return False

    async def _process_task(self, role: WorkerRole, payload: dict[str, Any], *, run_id: str, task_id: str) -> dict[str, Any]:
        if data_integrity_guard.halted():
            return {
                "status": "blocked",
                "reason": data_integrity_guard.halt_reason() or "system_halted",
                "run_id": run_id,
                "task_id": task_id,
                "role": role,
            }
        if role == "technical_analyst":
            return self._handle_analyst_report("technical_analyst", payload, run_id=run_id, task_id=task_id)
        if role == "fundamental_analyst":
            return self._handle_analyst_report("fundamental_analyst", payload, run_id=run_id, task_id=task_id)
        if role == "ml_timeseries_analyst":
            return self._handle_analyst_report("ml_timeseries_analyst", payload, run_id=run_id, task_id=task_id)
        if role == "insight_researcher":
            return self._handle_analyst_report("insight_researcher", payload, run_id=run_id, task_id=task_id)
        if role == "hedge_fund_researcher":
            return self._handle_analyst_report("hedge_fund_researcher", payload, run_id=run_id, task_id=task_id)
        if role == "sentiment_analyst":
            return self._handle_sentiment_analyst(payload, run_id=run_id, task_id=task_id)
        if role == "fund_manager":
            return self._handle_fund_manager(payload, run_id=run_id)
        if role == "trader":
            return self._handle_trader(payload, run_id=run_id)
        if role == "risk_auditor":
            return self._handle_risk_auditor(payload, run_id=run_id)
        if role == "blog_writer":
            return self._handle_blog_writer(payload, run_id=run_id)
        return {"status": "failed", "error": f"unsupported_role:{role}"}

    def _handle_analyst_report(
        self,
        role: AnalystRole,
        payload: dict[str, Any],
        *,
        run_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        symbol = str(payload.get("symbol") or payload.get("asset") or "SPY").upper().strip()
        if role == "technical_analyst":
            ingested = market_ingestion.build_technical_report(symbol)
        elif role == "fundamental_analyst":
            ingested = market_ingestion.build_fundamental_report(symbol)
        elif role == "ml_timeseries_analyst":
            ingested = market_ingestion.build_ml_timeseries_report(symbol)
        elif role == "insight_researcher":
            ingested = market_ingestion.build_insight_report(symbol)
        else:
            ingested = market_ingestion.build_hedge_fund_report(symbol)

        fallback_summary = str(payload.get("summary") or ingested.summary)
        fallback_findings = tuple(payload.get("findings") or ingested.findings or (ingested.summary,))
        fallback_confidence = _as_decimal(payload.get("confidence"), str(ingested.confidence))
        ai_analysis = ai_role_adapter.analyze_specialist(
            role=role,
            symbol=symbol,
            run_id=run_id,
            payload=payload,
            context={
                "ingested_summary": ingested.summary,
                "ingested_findings": list(ingested.findings),
                "ingested_metadata": dict(getattr(ingested, "metadata", {}) or {}),
                "ingested_provenance": [
                    {"source_type": ref.source_type, "source_id": ref.source_id}
                    for ref in getattr(ingested, "provenance", tuple())
                ],
            },
            fallback_summary=fallback_summary,
            fallback_findings=fallback_findings,
            fallback_confidence=fallback_confidence,
            fallback_provenance=tuple(getattr(ingested, "provenance", tuple())),
        )

        report_summary = ai_analysis.summary if ai_analysis else fallback_summary
        report_findings = ai_analysis.findings if ai_analysis else fallback_findings
        report_confidence = ai_analysis.confidence if ai_analysis else fallback_confidence
        merged_provenance = self._merge_provenance(
            base=tuple(getattr(ingested, "provenance", tuple())),
            citations=tuple(ai_analysis.citations) if ai_analysis else tuple(),
        )
        report = ContractResearchReport(
            run_id=run_id,
            agent_id=str(payload.get("worker_agent_id") or f"{role}_agent"),
            asset_universe=(symbol,),
            summary=report_summary,
            findings=report_findings,
            confidence=report_confidence,
            provenance=merged_provenance
            if merged_provenance
            else (ProvenanceRef(source_type="research", source_id=str(payload.get("source_id") or task_id)),),
        )
        saved = self._orchestrator.submit_research(report)
        return self._after_analyst_output(
            role=role,
            run_id=run_id,
            payload=payload,
            symbol=symbol,
            report_id=saved["report_id"],
            summary=report.summary,
            confidence=float(report.confidence),
            extra={
                "ingestion": dict(getattr(ingested, "metadata", {}) or {}),
                "ai_role_adapter": ai_analysis.metadata
                if ai_analysis
                else {"used": False, "provider": ai_role_adapter.health().get("provider")},
            },
        )

    def _handle_sentiment_analyst(self, payload: dict[str, Any], *, run_id: str, task_id: str) -> dict[str, Any]:
        symbol = str(payload.get("symbol") or payload.get("asset") or "SPY").upper().strip()
        ingested = market_ingestion.build_sentiment(symbol)
        snapshot = ContractSentimentSnapshot(
            run_id=run_id,
            agent_id=str(payload.get("worker_agent_id") or "sentiment_analyst_agent"),
            symbol=symbol,
            source=str(payload.get("source") or ingested.source),
            sentiment_score=float(payload.get("sentiment_score") if payload.get("sentiment_score") is not None else ingested.sentiment_score),
            confidence=float(payload.get("confidence") if payload.get("confidence") is not None else ingested.confidence),
            provenance_url=payload.get("provenance_url") or ingested.provenance_url,
        )
        saved_snapshot = self._orchestrator.submit_sentiment(snapshot)
        fallback_summary = (
            f"Sentiment analyst report for {symbol}: score={snapshot.sentiment_score:.3f}, confidence={snapshot.confidence:.3f}."
        )
        fallback_findings = (
            f"Aggregated sentiment score: {snapshot.sentiment_score:.3f}",
            f"Sentiment confidence: {snapshot.confidence:.3f}",
            f"Source: {snapshot.source}",
        )
        fallback_confidence = _as_decimal(snapshot.confidence, "0.5")
        fallback_provenance = (ProvenanceRef(source_type="sentiment", source_id=saved_snapshot["snapshot_id"]),)
        ai_analysis = ai_role_adapter.analyze_specialist(
            role="sentiment_analyst",
            symbol=symbol,
            run_id=run_id,
            payload=payload,
            context={
                "sentiment_snapshot": {
                    "snapshot_id": saved_snapshot["snapshot_id"],
                    "source": snapshot.source,
                    "sentiment_score": snapshot.sentiment_score,
                    "confidence": snapshot.confidence,
                    "provenance_url": snapshot.provenance_url,
                },
                "ingested_metadata": dict(ingested.metadata or {}),
            },
            fallback_summary=fallback_summary,
            fallback_findings=fallback_findings,
            fallback_confidence=fallback_confidence,
            fallback_provenance=fallback_provenance,
        )
        report_summary = ai_analysis.summary if ai_analysis else fallback_summary
        report_findings = ai_analysis.findings if ai_analysis else fallback_findings
        report_confidence = ai_analysis.confidence if ai_analysis else fallback_confidence
        merged_provenance = self._merge_provenance(
            base=fallback_provenance,
            citations=tuple(ai_analysis.citations) if ai_analysis else tuple(),
        )
        report = ContractResearchReport(
            run_id=run_id,
            agent_id=str(payload.get("worker_agent_id") or "sentiment_analyst_agent"),
            asset_universe=(symbol,),
            summary=report_summary,
            findings=report_findings,
            confidence=report_confidence,
            provenance=merged_provenance,
        )
        saved_report = self._orchestrator.submit_research(report)
        return self._after_analyst_output(
            role="sentiment_analyst",
            run_id=run_id,
            payload=payload,
            symbol=symbol,
            report_id=saved_report["report_id"],
            summary=report.summary,
            confidence=float(report.confidence),
            extra={
                "snapshot_id": saved_snapshot["snapshot_id"],
                "ai_role_adapter": ai_analysis.metadata
                if ai_analysis
                else {"used": False, "provider": ai_role_adapter.health().get("provider")},
            },
        )

    def _after_analyst_output(
        self,
        *,
        role: AnalystRole,
        run_id: str,
        payload: dict[str, Any],
        symbol: str,
        report_id: str,
        summary: str,
        confidence: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        signal_pack_id = str(payload.get("signal_pack_id") or "").strip()
        if signal_pack_id:
            swarm = self._register_signal_pack_output(
                signal_pack_id=signal_pack_id,
                role=role,
                run_id=run_id,
                symbol=symbol,
                payload=payload,
                report_id=report_id,
                summary=summary,
                confidence=confidence,
            )
            base = {"status": "completed", "report_id": report_id, "signal_pack_id": signal_pack_id, **dict(extra or {})}
            return {**base, **dict(swarm or {})}

        should_auto_blog = bool(payload.get("auto_publish_blog")) or role in {"insight_researcher", "hedge_fund_researcher"}
        blog_task_id = None
        if should_auto_blog:
            blog_task = self._task_bus.create_task(
                run_id=run_id,
                agent_id="blog_writer_agent",
                role="blog_writer",
                priority=6,
                payload={
                    "report_ids": [report_id],
                    "symbol": symbol,
                    "command": payload.get("command")
                    or (
                        f"Write a specific AI-fintech-hedge-fund editorial on {symbol}. "
                        "Use evidence from report findings, include execution scenarios, risk controls, and what to monitor next."
                    ),
                    "trigger_source": "research_auto_publish",
                    "metadata": {"origin_role": role},
                },
            )
            blog_task_id = blog_task.task_id

        handoff = self._task_bus.create_task(
            run_id=run_id,
            agent_id="fund_manager_agent",
            role="fund_manager",
            priority=8,
            payload={
                "report_ids": [report_id],
                "statement": payload.get("statement") or f"Analyst report handoff for {symbol}",
                "symbol": symbol,
                "side": str(payload.get("side") or "buy").lower(),
                "quantity": float(payload.get("quantity") or 1.0),
                "price": payload.get("price"),
                "sleeve": str(payload.get("sleeve") or "tactical"),
                "conviction": float(payload.get("conviction") or confidence),
                "metadata": {"origin_role": role, **dict(extra or {}), **dict(payload.get("metadata") or {})},
            },
        )
        return {
            "status": "completed",
            "report_id": report_id,
            "next_task_id": handoff.task_id,
            "next_role": "fund_manager",
            "blog_task_id": blog_task_id,
            **dict(extra or {}),
        }

    def _register_signal_pack_output(
        self,
        *,
        signal_pack_id: str,
        role: AnalystRole,
        run_id: str,
        symbol: str,
        payload: dict[str, Any],
        report_id: str,
        summary: str,
        confidence: float,
    ) -> dict[str, Any] | None:
        with self._signal_pack_lock:
            state = self._signal_packs.get(signal_pack_id)
            if state is None:
                expected = set(str(item) for item in payload.get("signal_pack_roles") or ANALYST_ROLES)
                expected = {item for item in expected if item in ANALYST_ROLES}
                if not expected:
                    expected = set(ANALYST_ROLES)
                state = SignalPackState(signal_pack_id=signal_pack_id, run_id=run_id, symbol=symbol, expected_roles=expected)
                self._signal_packs[signal_pack_id] = state

            state.outputs[role] = {"report_id": report_id, "summary": summary, "confidence": float(confidence)}
            ready = all(expected_role in state.outputs for expected_role in state.expected_roles)
            if not ready or state.dispatched:
                return None
            state.dispatched = True

        synthesis = self._dispatch_signal_pack_to_fund_manager(state=state, payload=payload)
        with self._signal_pack_lock:
            state.composite_report_id = synthesis.get("composite_report_id")
            state.fund_manager_task_id = synthesis.get("fund_manager_task_id")
        return synthesis

    def _dispatch_signal_pack_to_fund_manager(self, *, state: SignalPackState, payload: dict[str, Any]) -> dict[str, Any]:
        ordered_roles = [role for role in ANALYST_ROLES if role in state.outputs]
        findings: list[str] = ["Specialist analyst outputs:"]
        confidences: list[float] = []
        report_ids: list[str] = []
        for role in ordered_roles:
            output = state.outputs[role]
            report_ids.append(str(output["report_id"]))
            confidences.append(float(output["confidence"]))
            findings.append(f"{role}: {output['summary']}")

        aggregate_confidence = sum(confidences) / max(len(confidences), 1)
        composite = ContractResearchReport(
            run_id=state.run_id,
            agent_id="signal_committee_agent",
            asset_universe=(state.symbol,),
            summary=f"High-grade multi-signal report for {state.symbol} compiled from specialist analyst swarm.",
            findings=tuple(findings),
            confidence=_as_decimal(aggregate_confidence, "0.7"),
            provenance=tuple(ProvenanceRef(source_type="research", source_id=report_id) for report_id in report_ids),
        )
        saved = self._orchestrator.submit_research(composite)
        blog_task = self._task_bus.create_task(
            run_id=state.run_id,
            agent_id="blog_writer_agent",
            role="blog_writer",
            priority=8,
            payload={
                "report_ids": [saved["report_id"]],
                "symbol": state.symbol,
                "command": (
                    f"Write an institutional multi-signal editorial for {state.symbol} from the analyst swarm output. "
                    "Avoid generic framing, explain why the signal stack matters now, and include failure modes."
                ),
                "trigger_source": "signal_swarm",
                "metadata": {"signal_pack_id": state.signal_pack_id, "analyst_roles": ordered_roles},
            },
        )
        all_report_ids = [saved["report_id"], *report_ids]
        task = self._task_bus.create_task(
            run_id=state.run_id,
            agent_id="fund_manager_agent",
            role="fund_manager",
            priority=9,
            payload={
                "report_ids": all_report_ids,
                "statement": payload.get("statement") or f"Execute multi-signal thesis for {state.symbol} from high-grade analyst report.",
                "symbol": state.symbol,
                "side": str(payload.get("side") or "buy").lower(),
                "quantity": float(payload.get("quantity") or 1.0),
                "price": payload.get("price"),
                "sleeve": str(payload.get("sleeve") or "tactical"),
                "conviction": float(payload.get("conviction") or aggregate_confidence),
                "metadata": {
                    "signal_pack_id": state.signal_pack_id,
                    "analyst_roles": ordered_roles,
                    "aggregate_confidence": aggregate_confidence,
                    **dict(payload.get("metadata") or {}),
                },
            },
        )
        return {
            "signal_pack_complete": True,
            "composite_report_id": saved["report_id"],
            "fund_manager_task_id": task.task_id,
            "blog_task_id": blog_task.task_id,
        }

    def _merge_provenance(
        self,
        *,
        base: tuple[ProvenanceRef, ...],
        citations: tuple[str, ...],
    ) -> tuple[ProvenanceRef, ...]:
        merged = list(base)
        known_ids = {ref.source_id for ref in merged}
        for citation in citations:
            cleaned = str(citation).strip()
            if not cleaned or cleaned in known_ids:
                continue
            merged.append(ProvenanceRef(source_type="research", source_id=cleaned))
            known_ids.add(cleaned)
        return tuple(merged)

    def _handle_fund_manager(self, payload: dict[str, Any], *, run_id: str) -> dict[str, Any]:
        report_ids = list(payload.get("report_ids") or [])
        if not report_ids:
            return {"status": "failed", "error": "missing_report_ids"}
        symbol = str(payload.get("symbol") or "SPY").upper().strip()
        conviction = _to_float(payload.get("conviction"), 0.6)
        thesis = self._orchestrator.create_thesis(
            run_id=run_id,
            agent_id=str(payload.get("worker_agent_id") or "fund_manager_agent"),
            sleeve=_normalize_sleeve(payload.get("sleeve")),
            report_ids=report_ids,
            statement=str(payload.get("statement") or "System-generated thesis."),
            conviction=_as_decimal(conviction, "0.6"),
        )
        session = self._market_session()
        if self._allow_cash_hold and conviction < self._min_trade_conviction:
            return {
                "status": "completed",
                "thesis_id": thesis["thesis_id"],
                "decision": "hold_cash",
                "reason": "conviction_below_threshold",
                "symbol": symbol,
                "conviction": conviction,
                "min_trade_conviction": self._min_trade_conviction,
                "market_session": session,
            }
        if self._session_guard_enabled and self._block_trades_when_closed:
            if not session.get("open") or not session.get("trading_day"):
                return {
                    "status": "completed",
                    "thesis_id": thesis["thesis_id"],
                    "decision": "hold_cash",
                    "reason": str(session.get("reason") or "market_closed"),
                    "symbol": symbol,
                    "conviction": conviction,
                    "market_session": session,
                }
        trader_task = self._task_bus.create_task(
            run_id=run_id,
            agent_id="trader_agent",
            role="trader",
            priority=9,
            payload={
                "thesis_id": thesis["thesis_id"],
                "symbol": symbol,
                "side": str(payload.get("side") or "buy").lower(),
                "quantity": float(payload.get("quantity") or 1.0),
                "price": payload.get("price"),
                "metadata": {**dict(payload.get("metadata") or {}), "market_session": session},
            },
        )
        return {"status": "completed", "thesis_id": thesis["thesis_id"], "next_task_id": trader_task.task_id, "next_role": "trader"}

    def _handle_trader(self, payload: dict[str, Any], *, run_id: str) -> dict[str, Any]:
        if self._session_guard_enabled and self._block_trades_when_closed:
            session = self._market_session()
            if not session.get("open") or not session.get("trading_day"):
                return {
                    "status": "blocked",
                    "reason": str(session.get("reason") or "market_closed"),
                    "market_session": session,
                    "symbol": str(payload.get("symbol") or "SPY").upper().strip(),
                }
        result = self._orchestrator.execute_decision(
            run_id=run_id,
            agent_id=str(payload.get("worker_agent_id") or "trader_agent"),
            thesis_id=str(payload.get("thesis_id") or ""),
            symbol=str(payload.get("symbol") or "SPY"),
            side=str(payload.get("side") or "buy"),
            quantity=float(payload.get("quantity") or 1.0),
            price=float(payload["price"]) if payload.get("price") is not None else None,
            metadata={"origin": "fund_agent_runtime", **dict(payload.get("metadata") or {})},
        )
        if result.get("status") == "blocked":
            self._task_bus.create_task(
                run_id=run_id,
                agent_id="risk_auditor_agent",
                role="risk_auditor",
                priority=10,
                payload={"decision_id": result.get("decision_id"), "reasons": result.get("reasons", [])},
            )
            return {"status": "blocked", **result}
        return {"status": "completed", **result}

    def _handle_risk_auditor(self, payload: dict[str, Any], *, run_id: str) -> dict[str, Any]:
        blocked = self._orchestrator.list_blocked_trades(limit=int(payload.get("limit") or 20))
        pending = self._orchestrator.list_pending_decisions()
        return {"status": "completed", "run_id": run_id, "blocked_count": len(blocked), "pending_count": len(pending)}

    def _handle_blog_writer(self, payload: dict[str, Any], *, run_id: str) -> dict[str, Any]:
        report_ids = [str(item).strip() for item in (payload.get("report_ids") or []) if str(item).strip()]
        symbol = str(payload.get("symbol") or "").upper().strip()
        if not report_ids:
            recent = self._orchestrator.list_recent_research_reports(limit=int(payload.get("limit") or 3), symbol=symbol or None)
            report_ids = [str(item.get("report_id")) for item in recent if item.get("report_id")]
        if not report_ids:
            return {"status": "blocked", "reason": "no_research_reports_available"}

        posts = []
        for report_id in list(dict.fromkeys(report_ids)):
            report = self._orchestrator.get_research_report(report_id)
            if not report:
                continue
            post = blog_service.publish_from_research(
                report=report,
                command=str(
                    payload.get("command")
                    or (
                        "Write a high-signal AI-fintech-hedge-fund article with actionable context. "
                        "No generic commentary."
                    )
                ),
                trigger_source=str(payload.get("trigger_source") or "agent_runtime"),
            )
            posts.append(post)
        if not posts:
            return {"status": "blocked", "reason": "no_blog_post_generated", "report_ids": report_ids}
        return {
            "status": "completed",
            "published_count": len(posts),
            "post_ids": [str(item.get("id")) for item in posts if item.get("id")],
            "report_ids": report_ids,
        }


def _build_runtime() -> FundAgentRuntime:
    settings = get_settings()
    return FundAgentRuntime(
        enabled=settings.AGENT_RUNTIME_ENABLED,
        poll_interval_seconds=settings.AGENT_RUNTIME_POLL_INTERVAL_SECONDS,
        autopilot_enabled=settings.AGENT_RUNTIME_AUTOPILOT_ENABLED,
        autopilot_interval_seconds=settings.AGENT_RUNTIME_AUTOPILOT_INTERVAL_SECONDS,
        autopilot_symbols=_parse_symbol_csv(settings.AGENT_RUNTIME_AUTOPILOT_SYMBOLS),
        autopilot_dynamic_universe_enabled=settings.AGENT_RUNTIME_AUTOPILOT_DYNAMIC_UNIVERSE_ENABLED,
        autopilot_scout_symbols=_parse_symbol_csv(settings.AGENT_RUNTIME_AUTOPILOT_SCOUT_SYMBOLS),
        autopilot_scout_max_symbols=settings.AGENT_RUNTIME_AUTOPILOT_SCOUT_MAX_SYMBOLS,
        autopilot_default_side="sell" if settings.AGENT_RUNTIME_AUTOPILOT_DEFAULT_SIDE.strip().lower() == "sell" else "buy",
        autopilot_default_quantity=settings.AGENT_RUNTIME_AUTOPILOT_DEFAULT_QUANTITY,
        autopilot_sleeve=_normalize_sleeve(settings.AGENT_RUNTIME_AUTOPILOT_SLEEVE),
        session_guard_enabled=settings.AGENT_RUNTIME_SESSION_GUARD_ENABLED,
        block_trades_when_closed=settings.AGENT_RUNTIME_BLOCK_TRADES_WHEN_CLOSED,
        min_trade_conviction=settings.AGENT_RUNTIME_MIN_TRADE_CONVICTION,
        allow_cash_hold=settings.AGENT_RUNTIME_ALLOW_CASH_HOLD,
        blog_editorial_enabled=settings.BLOG_AUTO_EDITORIAL_ENABLED,
        blog_editorial_interval_hours=settings.BLOG_AUTO_EDITORIAL_INTERVAL_HOURS,
        blog_editorial_target_per_day=settings.BLOG_AUTO_EDITORIAL_TARGET_PER_DAY,
        blog_editorial_min_confidence=settings.BLOG_AUTO_EDITORIAL_MIN_CONFIDENCE,
    )


fund_agent_runtime = _build_runtime()
