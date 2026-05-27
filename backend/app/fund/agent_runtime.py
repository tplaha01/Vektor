from __future__ import annotations

import asyncio
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import RLock
from typing import Any, Iterable, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.core_engine import run_core_engine
from app.data.market_data import FEED
from app.data.news import latest_news
from app.fund.ai_role_adapter import TemporaryProviderCapacityError, ai_role_adapter
from app.fund.allocation_policy import infer_asset_class
from app.fund.ceo_service import vektor_ceo_service
from app.fund.contracts import (
    ProvenanceRef,
    ResearchReport as ContractResearchReport,
    SentimentSnapshot as ContractSentimentSnapshot,
    Sleeve,
)
from app.fund.blog_service import blog_service
from app.fund.core_engine_scoring import build_decision_scoring_from_signal
from app.fund.ingestion_adapters import market_ingestion
from app.fund.market_session import market_session_status
from app.fund.orchestrator import FirmOrchestrator, firm_orchestrator
from app.fund.runtime_guard import data_integrity_guard
from app.fund.task_bus import TaskBus, task_bus
from app.fund.agent_hierarchy import agent_hierarchy
from app.quant.regime import infer_market_regime
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


def _parse_weekday_name(value: str | None, fallback: int = 6) -> int:
    mapping = {
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tuesday": 1,
        "wed": 2,
        "wednesday": 2,
        "thu": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }
    return mapping.get(str(value or "").strip().lower(), fallback)


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
    status: str = "active"
    canceled_at: str | None = None
    canceled_reason: str | None = None


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
        swarm_wave_size: int = 2,
        swarm_wave_spacing_seconds: float = 20.0,
        swarm_max_active_packs: int = 2,
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
        blog_market_report_scheduler_interval_seconds: float = 300.0,
        blog_premarket_report_enabled: bool = True,
        blog_premarket_report_lead_minutes: int = 30,
        blog_postmarket_report_enabled: bool = True,
        blog_postmarket_report_delay_minutes: int = 20,
        blog_weekahead_report_enabled: bool = True,
        blog_weekahead_report_weekday: int = 6,
        blog_weekahead_report_hour_et: int = 18,
        blog_weekahead_report_minute_et: int = 0,
        blog_market_report_symbols: Iterable[str] | None = None,
        ceo_digest_enabled: bool = True,
        ceo_digest_interval_seconds: float = 21600.0,
        discovery_min_score: float = 0.58,
        discovery_min_confidence: float = 0.55,
        discovery_news_limit: int = 8,
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
        self._canceled_runs: dict[str, dict[str, Any]] = {}
        self._canceled_signal_packs: dict[str, dict[str, Any]] = {}
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
        self._swarm_wave_size = max(1, int(swarm_wave_size))
        self._swarm_wave_spacing_seconds = max(1.0, float(swarm_wave_spacing_seconds))
        self._swarm_max_active_packs = max(1, int(swarm_max_active_packs))
        self._scheduled_swarm_waves: list[dict[str, Any]] = []
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
        self._blog_market_report_scheduler_interval_seconds = max(60.0, float(blog_market_report_scheduler_interval_seconds))
        self._blog_editorial_target_per_day = max(0, int(blog_editorial_target_per_day))
        self._blog_editorial_min_confidence = max(0.0, min(1.0, float(blog_editorial_min_confidence)))
        self._blog_premarket_report_enabled = bool(blog_premarket_report_enabled)
        self._blog_premarket_report_lead_minutes = max(1, int(blog_premarket_report_lead_minutes))
        self._blog_postmarket_report_enabled = bool(blog_postmarket_report_enabled)
        self._blog_postmarket_report_delay_minutes = max(0, int(blog_postmarket_report_delay_minutes))
        self._blog_weekahead_report_enabled = bool(blog_weekahead_report_enabled)
        self._blog_weekahead_report_weekday = max(0, min(6, int(blog_weekahead_report_weekday)))
        self._blog_weekahead_report_hour_et = max(0, min(23, int(blog_weekahead_report_hour_et)))
        self._blog_weekahead_report_minute_et = max(0, min(59, int(blog_weekahead_report_minute_et)))
        self._blog_market_report_symbols = tuple(
            dict.fromkeys(str(item).strip().upper() for item in (blog_market_report_symbols or ()) if str(item).strip())
        ) or ("SPY", "QQQ", "AAPL", "MSFT", "NVDA")
        self._market_timezone = ZoneInfo("America/New_York")
        self._blog_editorial_task: asyncio.Task | None = None
        self._blog_editorial_cycles = 0
        self._blog_editorial_enqueued = 0
        self._blog_editorial_last_run_id: str | None = None
        self._blog_editorial_last_run_at: str | None = None
        self._blog_editorial_last_error: str | None = None
        self._ceo_digest_enabled = bool(ceo_digest_enabled)
        self._ceo_digest_interval_seconds = max(300.0, float(ceo_digest_interval_seconds))
        self._ceo_digest_task: asyncio.Task | None = None
        self._ceo_digest_cycles = 0
        self._ceo_digest_last_digest_id: str | None = None
        self._ceo_digest_last_run_at: str | None = None
        self._ceo_digest_last_error: str | None = None
        self._discovery_min_score = max(0.0, min(1.0, float(discovery_min_score)))
        self._discovery_min_confidence = max(0.0, min(1.0, float(discovery_min_confidence)))
        self._discovery_news_limit = max(1, int(discovery_news_limit))

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
        if self._ceo_digest_enabled:
            self._ceo_digest_task = asyncio.create_task(self._ceo_digest_loop(), name="fund-ceo-digest")

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
        if self._ceo_digest_task is not None:
            tasks.append(self._ceo_digest_task)
            self._ceo_digest_task = None
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
                "swarm_wave_size": self._swarm_wave_size,
                "swarm_wave_spacing_seconds": self._swarm_wave_spacing_seconds,
                "swarm_max_active_packs": self._swarm_max_active_packs,
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
                "scheduled_wave_count": len(self._scheduled_swarm_waves),
                "next_wave_at": self._scheduled_swarm_waves[0]["scheduled_for"] if self._scheduled_swarm_waves else None,
            }
            blog_editorial = {
                "enabled": self._blog_editorial_enabled,
                "running": self._blog_editorial_task is not None and not self._blog_editorial_task.done(),
                "interval_seconds": self._blog_market_report_scheduler_interval_seconds,
                "target_per_day": self._blog_editorial_target_per_day,
                "min_confidence": self._blog_editorial_min_confidence,
                "premarket_enabled": self._blog_premarket_report_enabled,
                "premarket_lead_minutes": self._blog_premarket_report_lead_minutes,
                "postmarket_enabled": self._blog_postmarket_report_enabled,
                "postmarket_delay_minutes": self._blog_postmarket_report_delay_minutes,
                "weekahead_enabled": self._blog_weekahead_report_enabled,
                "weekahead_weekday": self._blog_weekahead_report_weekday,
                "weekahead_hour_et": self._blog_weekahead_report_hour_et,
                "weekahead_minute_et": self._blog_weekahead_report_minute_et,
                "market_report_symbols": list(self._blog_market_report_symbols),
                "cycles": self._blog_editorial_cycles,
                "enqueued_count": self._blog_editorial_enqueued,
                "last_run_id": self._blog_editorial_last_run_id,
                "last_run_at": self._blog_editorial_last_run_at,
                "last_error": self._blog_editorial_last_error,
            }
            ceo_digest = {
                "enabled": self._ceo_digest_enabled,
                "running": self._ceo_digest_task is not None and not self._ceo_digest_task.done(),
                "interval_seconds": self._ceo_digest_interval_seconds,
                "cycles": self._ceo_digest_cycles,
                "last_digest_id": self._ceo_digest_last_digest_id,
                "last_run_at": self._ceo_digest_last_run_at,
                "last_error": self._ceo_digest_last_error,
            }
            halt_guard = {
                "halted": data_integrity_guard.halted(),
                "reason": data_integrity_guard.halt_reason(),
                "last_queue_drain_reason": self._last_halt_drain_reason,
            }
        with self._signal_pack_lock:
            active_pack_count = sum(
                1
                for state in self._signal_packs.values()
                if state.status != "canceled" and set(state.outputs.keys()) != set(state.expected_roles)
            )
            packs = [
                {
                    "signal_pack_id": state.signal_pack_id,
                    "run_id": state.run_id,
                    "symbol": state.symbol,
                    "expected_roles": sorted(state.expected_roles),
                    "completed_roles": sorted(state.outputs.keys()),
                    "missing_roles": sorted(set(state.expected_roles) - set(state.outputs.keys())),
                    "progress_ratio": round(len(state.outputs) / max(len(state.expected_roles), 1), 3),
                    "dispatched": state.dispatched,
                    "composite_report_id": state.composite_report_id,
                    "fund_manager_task_id": state.fund_manager_task_id,
                    "status": state.status,
                    "canceled_at": state.canceled_at,
                    "canceled_reason": state.canceled_reason,
                }
                for state in self._signal_packs.values()
            ]
            swarm_waves = []
            now = datetime.now(timezone.utc)
            for wave in self._scheduled_swarm_waves:
                scheduled_raw = str(wave.get("scheduled_for") or now.isoformat())
                scheduled_for = datetime.fromisoformat(scheduled_raw.replace("Z", "+00:00"))
                due_in_seconds = max(0.0, round((scheduled_for - now).total_seconds(), 1))
                active_symbols = {
                    state.symbol.upper().strip()
                    for state in self._signal_packs.values()
                    if state.run_id == str(wave.get("run_id") or "").strip() and state.status != "canceled"
                }
                matched_pack_ids = [
                    state.signal_pack_id
                    for state in self._signal_packs.values()
                    if state.run_id == str(wave.get("run_id") or "").strip()
                    and state.symbol.upper().strip() in {str(item).upper().strip() for item in (wave.get("symbols") or [])}
                ]
                if due_in_seconds <= 0 and active_pack_count >= self._swarm_max_active_packs:
                    dispatch_status = "deferred"
                elif due_in_seconds <= 0:
                    dispatch_status = "due"
                elif due_in_seconds <= self._swarm_wave_spacing_seconds:
                    dispatch_status = "imminent"
                else:
                    dispatch_status = "queued"
                swarm_waves.append(
                    {
                        **wave,
                        "dispatch_status": dispatch_status,
                        "due_in_seconds": due_in_seconds,
                        "active_symbol_count": len(active_symbols),
                        "matched_signal_pack_ids": matched_pack_ids,
                        "capacity_remaining": max(0, self._swarm_max_active_packs - active_pack_count),
                    }
                )
            swarm_scheduler = {
                "scheduled_count": len(swarm_waves),
                "due_count": sum(1 for wave in swarm_waves if wave.get("dispatch_status") == "due"),
                "deferred_count": sum(1 for wave in swarm_waves if wave.get("dispatch_status") == "deferred"),
                "imminent_count": sum(1 for wave in swarm_waves if wave.get("dispatch_status") == "imminent"),
                "active_pack_count": active_pack_count,
                "max_active_packs": self._swarm_max_active_packs,
                "capacity_remaining": max(0, self._swarm_max_active_packs - active_pack_count),
            }
        pending_decisions = self._orchestrator.list_pending_decisions()
        active_contexts = []
        for item in self._orchestrator.list_active_tasks():
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            active_contexts.append(
                {
                    "task_id": item.get("task_id"),
                    "run_id": item.get("run_id"),
                    "role": item.get("role"),
                    "agent_id": item.get("agent_id"),
                    "symbol": payload.get("symbol"),
                    "command": payload.get("command"),
                    "decision_id": payload.get("decision_id"),
                    "signal_pack_id": payload.get("signal_pack_id"),
                    "context": payload,
                }
            )
        discovery_rows = self._orchestrator.list_discovery_opportunities(limit=24)
        discovery_status_counts: dict[str, int] = {}
        latest_no_trade = None
        for row in discovery_rows:
            status = str(row.get("status") or "candidate")
            discovery_status_counts[status] = int(discovery_status_counts.get(status, 0)) + 1
            if latest_no_trade is None and status == "no_trade":
                latest_no_trade = row
        return {
            "enabled": self._enabled,
            "started": self._started,
            "poll_interval_seconds": self._poll_interval_seconds,
            "workers": workers,
            "autopilot": autopilot,
            "signal_packs": packs,
            "swarm_waves": swarm_waves,
            "swarm_scheduler": swarm_scheduler,
            "canceled_runs": list(self._canceled_runs.values()),
            "canceled_signal_packs": list(self._canceled_signal_packs.values()),
            "active_contexts": active_contexts,
            "pending_decisions": pending_decisions[:8],
            "discovery": {
                "count": len(discovery_rows),
                "top": discovery_rows[:8],
                "status_counts": discovery_status_counts,
                "latest_no_trade": latest_no_trade,
            },
            "ai_role_adapter": ai_role_adapter.health(),
            "data_integrity": data_integrity_guard.status(),
            "halt_guard": halt_guard,
            "blog_editorial": blog_editorial,
            "ceo_digest": ceo_digest,
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
        self._process_due_swarm_waves()
        cycle_run_id = run_id or f"run-autopilot-{uuid4().hex[:12]}"
        result = self._enqueue_autopilot_cycle(cycle_run_id)
        result["accepted"] = True
        result["manual"] = True
        return result

    def cancel_run(self, *, run_id: str, reason: str = "operator_cancel") -> dict[str, Any]:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            return {"accepted": False, "reason": "missing_run_id"}
        canceled_at = _utc_iso()
        self._canceled_runs[clean_run_id] = {"run_id": clean_run_id, "reason": reason, "canceled_at": canceled_at}
        blocked = 0
        task_ids: list[str] = []
        for task in self._task_bus.list_tasks():
            if task.run_id != clean_run_id or task.status not in {"queued", "running"}:
                continue
            self._task_bus.set_status(task.task_id, "blocked", {"reason": reason, "run_id": clean_run_id, "canceled": True})
            blocked += 1
            task_ids.append(task.task_id)
        canceled_packs: list[str] = []
        with self._signal_pack_lock:
            for state in self._signal_packs.values():
                if state.run_id != clean_run_id:
                    continue
                state.status = "canceled"
                state.canceled_at = canceled_at
                state.canceled_reason = reason
                self._canceled_signal_packs[state.signal_pack_id] = {
                    "signal_pack_id": state.signal_pack_id,
                    "run_id": clean_run_id,
                    "reason": reason,
                    "canceled_at": canceled_at,
                }
                canceled_packs.append(state.signal_pack_id)
            self._scheduled_swarm_waves = [wave for wave in self._scheduled_swarm_waves if str(wave.get("run_id") or "") != clean_run_id]
        return {
            "accepted": True,
            "run_id": clean_run_id,
            "blocked_task_count": blocked,
            "task_ids": task_ids,
            "canceled_signal_pack_ids": canceled_packs,
            "canceled_at": canceled_at,
        }

    def cancel_signal_pack(self, *, signal_pack_id: str, reason: str = "operator_cancel") -> dict[str, Any]:
        clean_signal_pack_id = str(signal_pack_id or "").strip()
        if not clean_signal_pack_id:
            return {"accepted": False, "reason": "missing_signal_pack_id"}
        canceled_at = _utc_iso()
        with self._signal_pack_lock:
            state = self._signal_packs.get(clean_signal_pack_id)
            if state is None:
                return {"accepted": False, "reason": "unknown_signal_pack_id"}
            state.status = "canceled"
            state.canceled_at = canceled_at
            state.canceled_reason = reason
            self._canceled_signal_packs[clean_signal_pack_id] = {
                "signal_pack_id": clean_signal_pack_id,
                "run_id": state.run_id,
                "reason": reason,
                "canceled_at": canceled_at,
            }
            self._scheduled_swarm_waves = [
                {
                    **wave,
                    "symbols": [symbol for symbol in (wave.get("symbols") or []) if symbol.upper().strip() != state.symbol.upper().strip()],
                }
                for wave in self._scheduled_swarm_waves
                if str(wave.get("run_id") or "") != state.run_id or any(
                    symbol.upper().strip() != state.symbol.upper().strip() for symbol in (wave.get("symbols") or [])
                )
            ]
        blocked = 0
        task_ids: list[str] = []
        for task in self._task_bus.list_tasks():
            if str(task.payload.get("signal_pack_id") or "").strip() != clean_signal_pack_id:
                continue
            if task.status not in {"queued", "running"}:
                continue
            self._task_bus.set_status(task.task_id, "blocked", {"reason": reason, "signal_pack_id": clean_signal_pack_id, "canceled": True})
            blocked += 1
            task_ids.append(task.task_id)
        return {
            "accepted": True,
            "signal_pack_id": clean_signal_pack_id,
            "run_id": state.run_id,
            "blocked_task_count": blocked,
            "task_ids": task_ids,
            "canceled_at": canceled_at,
        }

    def reroute_signal_pack(
        self,
        *,
        signal_pack_id: str,
        assigned_roles: Iterable[str],
        reason: str = "operator_reroute",
    ) -> dict[str, Any]:
        clean_signal_pack_id = str(signal_pack_id or "").strip()
        if not clean_signal_pack_id:
            return {"accepted": False, "reason": "missing_signal_pack_id"}
        normalized_roles = {role for role in (str(item).strip().lower() for item in assigned_roles) if role in ANALYST_ROLES}
        if not normalized_roles:
            return {"accepted": False, "reason": "no_valid_roles"}
        with self._signal_pack_lock:
            state = self._signal_packs.get(clean_signal_pack_id)
            if state is None:
                return {"accepted": False, "reason": "unknown_signal_pack_id"}
            if state.status == "canceled":
                return {"accepted": False, "reason": "signal_pack_canceled"}
            state.expected_roles = set(normalized_roles)
            state.dispatched = all(role in state.outputs for role in state.expected_roles)
            run_id = state.run_id
            symbol = state.symbol
        queued_task_ids: list[str] = []
        for role in sorted(normalized_roles):
            if self._has_existing_pack_task(signal_pack_id=clean_signal_pack_id, role=role) or self._has_completed_pack_output(signal_pack_id=clean_signal_pack_id, role=role):
                continue
            task = self._task_bus.create_task(
                run_id=run_id,
                agent_id="openclaw_orchestrator",
                role=role,
                priority=9,
                payload={
                    "command": f"rerouted specialist task for {symbol}",
                    "symbol": symbol,
                    "side": self._autopilot_default_side,
                    "quantity": self._autopilot_default_quantity,
                    "sleeve": self._autopilot_sleeve.value,
                    "signal_pack_id": clean_signal_pack_id,
                    "signal_pack_roles": sorted(normalized_roles),
                    "metadata": {"rerouted": True, "reason": reason},
                },
            )
            queued_task_ids.append(task.task_id)
        return {
            "accepted": True,
            "signal_pack_id": clean_signal_pack_id,
            "run_id": run_id,
            "expected_roles": sorted(normalized_roles),
            "queued_task_ids": queued_task_ids,
        }

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
            except TemporaryProviderCapacityError as exc:
                deferred = self._task_bus.defer_task(
                    task.task_id,
                    reason=str(exc),
                    retry_after_seconds=exc.retry_after_seconds,
                    extra_details={
                        "reasons": list(exc.reasons or []),
                        "providers": list(exc.providers or []),
                        "defer_type": "provider_capacity",
                    },
                )
                with self._state_lock:
                    state = self._states[role]
                    state.last_task_status = "queued"
                    state.last_error = f"deferred_until_capacity:{exc.retry_after_seconds:.1f}s"

                    agent_id = f"agent-{role}"
                    next_attempt_at = None
                    if deferred is not None:
                        scheduler = deferred.payload.get("_scheduler") if isinstance(deferred.payload, dict) else {}
                        if isinstance(scheduler, dict):
                            next_attempt_at = scheduler.get("next_attempt_at")
                    agent_hierarchy.update_agent_status(
                        agent_id=agent_id,
                        role=role,
                        status="idle",
                        last_task_id=task.task_id,
                        last_task_status="queued",
                        last_error=state.last_error,
                        task_count=state.completed_count + state.failed_count + state.blocked_count,
                        success_count=state.completed_count,
                        failed_count=state.failed_count,
                        blocked_count=state.blocked_count,
                    )
                    publish_agent_event("agent.task_deferred", {
                        "agent_id": agent_id,
                        "role": role,
                        "task_id": task.task_id,
                        "status": "queued",
                        "retry_after_seconds": round(exc.retry_after_seconds, 2),
                        "next_attempt_at": next_attempt_at,
                        "reason": str(exc),
                        "reasons": list(exc.reasons or []),
                    })
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
                self._process_due_swarm_waves()
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
                    await asyncio.sleep(self._blog_market_report_scheduler_interval_seconds)
                    continue

                cycle_run_id = f"run-blog-editorial-{uuid4().hex[:10]}"
                self._enqueue_blog_editorial_cycle(cycle_run_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self._state_lock:
                    self._blog_editorial_last_error = str(exc)
                    self._blog_editorial_last_run_at = _utc_iso()
            await asyncio.sleep(self._blog_market_report_scheduler_interval_seconds)

    async def _ceo_digest_loop(self) -> None:
        while True:
            try:
                digest = vektor_ceo_service.persist_digest(digest_type="scheduled", generated_by="vektor")
                with self._state_lock:
                    self._ceo_digest_cycles += 1
                    self._ceo_digest_last_digest_id = str(digest.get("digest_id") or "")
                    self._ceo_digest_last_run_at = _utc_iso()
                    self._ceo_digest_last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self._state_lock:
                    self._ceo_digest_last_error = str(exc)
                    self._ceo_digest_last_run_at = _utc_iso()
            await asyncio.sleep(self._ceo_digest_interval_seconds)

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
        wave_plan = self._plan_swarm_waves(run_id=run_id, selected_symbols=selected_symbols)
        queued_ids = self._process_due_swarm_waves()

        with self._state_lock:
            self._autopilot_cycles += 1
            self._autopilot_enqueued += len(queued_ids)
            self._autopilot_last_run_id = run_id
            self._autopilot_last_run_at = _utc_iso()
            self._autopilot_last_error = None
            self._autopilot_last_session = dict(session)
            self._autopilot_last_scout = {
                **dict(scout_meta),
                **wave_plan,
            }

        return {
            "run_id": run_id,
            "enqueued_count": len(queued_ids),
            "task_ids": queued_ids,
            "symbol_count": len(selected_symbols),
            "selected_symbols": list(selected_symbols),
            "session": session,
            "scout": {**dict(scout_meta), **wave_plan},
        }

    def _market_session(self) -> dict[str, Any]:
        return market_session_status(get_settings())

    def _record_discovery_status(
        self,
        opportunity: dict[str, Any],
        *,
        status: str,
        reason: str,
        rank: int | None = None,
        selected: bool = False,
        threshold_passed: bool | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = dict(opportunity.get("metadata") or {})
        metadata.update(
            {
                "discovery_status": status,
                "discovery_reason": reason,
                "selected_for_wave": selected,
            }
        )
        if rank is not None:
            metadata["discovery_rank"] = int(rank)
        if threshold_passed is not None:
            metadata["threshold_passed"] = bool(threshold_passed)
            metadata["thresholds"] = {
                "min_score": self._discovery_min_score,
                "min_confidence": self._discovery_min_confidence,
            }
        if extra_metadata:
            metadata.update(dict(extra_metadata))
        return self._orchestrator.record_discovery_opportunity(
            {
                **dict(opportunity),
                "metadata": metadata,
                "status": status,
            }
        )

    def _record_no_trade_discovery(
        self,
        *,
        run_id: str,
        reason: str,
        candidate_count: int,
        top_scores: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        return self._orchestrator.record_discovery_opportunity(
            {
                "opportunity_id": f"opportunity-no-trade-{run_id}-{now.strftime('%Y%m%d%H%M%S')}",
                "run_id": run_id,
                "agent_id": "world_scanner",
                "symbol": "CASH",
                "asset_class": "equities",
                "strategy_family": "capital_preservation",
                "direction": "hold_cash",
                "score": 0.0,
                "confidence": 1.0,
                "horizon": "intraday",
                "thesis": "Dynamic scout did not find any symbol that cleared the current discovery thresholds, so Vektor is holding cash.",
                "catalysts": ["capital_preservation", "no_trade"],
                "evidence": [
                    f"Discovery selected no symbols because {reason}.",
                    f"Candidate count: {candidate_count}.",
                ],
                "ml": {
                    "math_summary": f"no_trade because {reason}",
                    "candidate_count": int(candidate_count),
                },
                "metadata": {
                    "source": "autopilot_dynamic_universe",
                    "discovery_status": "no_trade",
                    "discovery_reason": reason,
                    "candidate_count": int(candidate_count),
                    "top_scores": list(top_scores or []),
                },
                "status": "no_trade",
                "discovered_at": now.isoformat().replace("+00:00", "Z"),
            }
        )

    def _resolve_autopilot_symbols(self) -> tuple[tuple[str, ...], dict[str, Any]]:
        if not self._autopilot_dynamic_universe_enabled:
            selected = tuple(self._autopilot_symbols[: self._autopilot_scout_max_symbols])
            return selected, {
                "dynamic_universe_enabled": False,
                "candidate_count": len(self._autopilot_symbols),
                "selected_symbols": list(selected),
            }

        scored: list[dict[str, Any]] = []
        for symbol in self._autopilot_scout_symbols:
            opportunity = self._score_autopilot_symbol(symbol)
            if opportunity is None:
                continue
            scored.append(opportunity)

        run_id = self._autopilot_last_run_id or "autopilot-discovery"
        thresholds = {
            "min_score": self._discovery_min_score,
            "min_confidence": self._discovery_min_confidence,
        }

        if not scored:
            fallback = tuple(self._autopilot_symbols[: self._autopilot_scout_max_symbols]) if not self._allow_cash_hold else ()
            if not fallback:
                self._record_no_trade_discovery(
                    run_id=run_id,
                    reason="scout_no_scores",
                    candidate_count=len(self._autopilot_scout_symbols),
                )
            return fallback, {
                "dynamic_universe_enabled": True,
                "candidate_count": len(self._autopilot_scout_symbols),
                "selected_symbols": list(fallback),
                "reason": "scout_no_scores_fallback_to_seed" if fallback else "no_trade_candidates_meet_threshold",
                "thresholds": thresholds,
            }

        scored.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("symbol") or "")))
        qualified: list[dict[str, Any]] = []
        pruned_threshold = 0
        for index, item in enumerate(scored, start=1):
            score_ok = float(item.get("score") or 0.0) >= self._discovery_min_score
            confidence_ok = float(item.get("confidence") or 0.0) >= self._discovery_min_confidence
            if score_ok and confidence_ok:
                qualified.append(item)
                item.update(self._record_discovery_status(
                    item,
                    status="qualified",
                    reason="passed_thresholds",
                    rank=index,
                    threshold_passed=True,
                ))
                continue
            pruned_threshold += 1
            prune_reason = "score_below_threshold" if not score_ok else "confidence_below_threshold"
            item.update(self._record_discovery_status(
                item,
                status="pruned_threshold",
                reason=prune_reason,
                rank=index,
                threshold_passed=False,
            ))

        top_scored = [
            {
                "symbol": str(item.get("symbol") or ""),
                "score": round(float(item.get("score") or 0.0), 4),
                "confidence": round(float(item.get("confidence") or 0.0), 4),
                "asset_class": item.get("asset_class"),
                "direction": item.get("direction"),
                "status": item.get("status"),
            }
            for item in scored[:5]
        ]
        if (
            not qualified
            and self._allow_cash_hold
            and len(self._autopilot_scout_symbols) > self._autopilot_scout_max_symbols
        ):
            self._record_no_trade_discovery(
                run_id=run_id,
                reason="thresholds_not_met",
                candidate_count=len(scored),
                top_scores=top_scored,
            )
            return (), {
                "dynamic_universe_enabled": True,
                "candidate_count": len(self._autopilot_scout_symbols),
                "selected_symbols": [],
                "reason": "no_trade_candidates_meet_threshold",
                "thresholds": thresholds,
                "top_scores": top_scored,
                "qualified_count": 0,
                "pruned_threshold_count": pruned_threshold,
                "status_counts": {
                    "qualified": 0,
                    "pruned_threshold": pruned_threshold,
                    "candidate": len(scored),
                    "no_trade": 1,
                },
            }

        pool = qualified or scored
        selected = tuple(str(item.get("symbol") or "") for item in pool[: self._autopilot_scout_max_symbols])
        selected_set = {symbol for symbol in selected if symbol}
        selected_count = 0
        pruned_capacity = 0
        for index, item in enumerate(pool, start=1):
            symbol = str(item.get("symbol") or "")
            if symbol in selected_set:
                selected_count += 1
                item.update(self._record_discovery_status(
                    item,
                    status="selected",
                    reason="queued_for_wave",
                    rank=index,
                    selected=True,
                    threshold_passed=item in qualified if qualified else None,
                    extra_metadata={"selected_rank": selected_count},
                ))
                continue
            pruned_capacity += 1
            item.update(self._record_discovery_status(
                item,
                status="pruned_capacity",
                reason="wave_capacity_limit",
                rank=index,
                threshold_passed=item in qualified if qualified else None,
            ))
        return selected, {
            "dynamic_universe_enabled": True,
            "candidate_count": len(self._autopilot_scout_symbols),
            "selected_symbols": list(selected),
            "qualified_count": len(qualified),
            "pruned_threshold_count": pruned_threshold,
            "pruned_capacity_count": pruned_capacity,
            "thresholds": thresholds,
            "status_counts": {
                "selected": selected_count,
                "qualified": len(qualified),
                "pruned_threshold": pruned_threshold,
                "pruned_capacity": pruned_capacity,
            },
            "top_scores": [
                {
                    "symbol": str(item.get("symbol") or ""),
                    "score": round(float(item.get("score") or 0.0), 4),
                    "confidence": round(float(item.get("confidence") or 0.0), 4),
                    "asset_class": item.get("asset_class"),
                    "direction": item.get("direction"),
                    "status": item.get("status"),
                    "reason": (item.get("metadata") or {}).get("discovery_reason"),
                }
                for item in pool[:5]
            ],
        }

    def _active_signal_pack_count(self) -> int:
        with self._signal_pack_lock:
            return sum(
                1
                for state in self._signal_packs.values()
                if set(state.outputs.keys()) != set(state.expected_roles)
            )

    def _schedule_swarm_wave(
        self,
        *,
        run_id: str,
        symbols: list[str],
        scheduled_for: datetime,
        wave_index: int,
        total_waves: int,
    ) -> None:
        if not symbols:
            return
        self._scheduled_swarm_waves.append(
            {
                "run_id": run_id,
                "symbols": list(symbols),
                "scheduled_for": scheduled_for.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "wave_index": wave_index,
                "total_waves": total_waves,
            }
        )
        self._scheduled_swarm_waves.sort(key=lambda item: (item.get("scheduled_for") or "", item.get("wave_index") or 0))

    def _plan_swarm_waves(self, *, run_id: str, selected_symbols: tuple[str, ...]) -> dict[str, Any]:
        symbols = [symbol for symbol in selected_symbols if symbol and not self._has_inflight_analyst_tasks(symbol=symbol)]
        self._scheduled_swarm_waves = [wave for wave in self._scheduled_swarm_waves if str(wave.get("run_id") or "") != run_id]
        if not symbols:
            return {
                "wave_count": 0,
                "scheduled_wave_count": len(self._scheduled_swarm_waves),
                "wave_symbols": [],
            }

        waves = [symbols[index:index + self._swarm_wave_size] for index in range(0, len(symbols), self._swarm_wave_size)]
        now = datetime.now(timezone.utc)
        for wave_index, wave_symbols in enumerate(waves, start=1):
            scheduled_for = now + timedelta(seconds=(wave_index - 1) * self._swarm_wave_spacing_seconds)
            self._schedule_swarm_wave(
                run_id=run_id,
                symbols=wave_symbols,
                scheduled_for=scheduled_for,
                wave_index=wave_index,
                total_waves=len(waves),
            )
        return {
            "wave_count": len(waves),
            "scheduled_wave_count": len(self._scheduled_swarm_waves),
            "wave_symbols": [list(wave) for wave in waves],
            "next_wave_at": self._scheduled_swarm_waves[0]["scheduled_for"] if self._scheduled_swarm_waves else None,
        }

    def _process_due_swarm_waves(self) -> list[str]:
        now = datetime.now(timezone.utc)
        queued_ids: list[str] = []
        keep: list[dict[str, Any]] = []
        for wave in self._scheduled_swarm_waves:
            scheduled_for = datetime.fromisoformat(str(wave.get("scheduled_for") or now.isoformat()).replace("Z", "+00:00"))
            if scheduled_for > now:
                keep.append(wave)
                continue
            if self._active_signal_pack_count() >= self._swarm_max_active_packs:
                rescheduled_for = now + timedelta(seconds=self._swarm_wave_spacing_seconds)
                wave["scheduled_for"] = rescheduled_for.replace(microsecond=0).isoformat().replace("+00:00", "Z")
                keep.append(wave)
                continue
            for symbol in wave.get("symbols") or []:
                if self._has_inflight_analyst_tasks(symbol=symbol):
                    continue
                swarm = self.enqueue_signal_swarm(
                    run_id=str(wave.get("run_id") or f"run-autopilot-{uuid4().hex[:12]}"),
                    symbol=str(symbol).upper().strip(),
                    agent_id="autopilot_coordinator",
                    command=f"autopilot swarm {symbol}",
                    payload={
                        "side": self._autopilot_default_side,
                        "quantity": self._autopilot_default_quantity,
                        "sleeve": self._autopilot_sleeve.value,
                        "metadata": {
                            "autopilot": True,
                            "wave_index": wave.get("wave_index"),
                            "total_waves": wave.get("total_waves"),
                            "scheduled_for": wave.get("scheduled_for"),
                        },
                    },
                    priority=7,
                )
                queued_ids.extend(list(swarm.get("task_ids") or []))
        self._scheduled_swarm_waves = keep
        return queued_ids

    def _score_autopilot_symbol(self, symbol: str) -> dict[str, Any] | None:
        normalized = str(symbol or "").upper().strip()
        if not normalized:
            return None
        try:
            technical = market_ingestion.build_technical_report(normalized)
            ml = market_ingestion.build_ml_timeseries_report(normalized)
            sentiment = market_ingestion.build_sentiment(normalized)
            history = FEED.history(normalized, bars=60)
            news_rows = latest_news(normalized, limit=self._discovery_news_limit)
            regime_snapshot = infer_market_regime(history)
        except Exception:
            return None

        ml_prob_up = _extract_metric(ml.findings, "Directional probability(up)")
        if ml_prob_up is None:
            ml_prob_up = 0.5
        ml_prob_up = max(0.0, min(1.0, float(ml_prob_up)))
        sentiment_norm = max(0.0, min(1.0, (_to_float(sentiment.sentiment_score, 0.0) + 1.0) / 2.0))
        tech_conf = max(0.0, min(1.0, _to_float(technical.confidence, 0.5)))
        ml_conf = max(0.0, min(1.0, _to_float(ml.confidence, 0.5)))
        closes = []
        volumes = []
        if hasattr(history, "empty") and not history.empty:
            try:
                closes = [float(value) for value in list(history["close"].tail(30)) if value is not None]
                volumes = [float(value) for value in list(history["volume"].tail(30)) if value is not None]
            except Exception:
                closes = []
                volumes = []
        liquidity_score = 0.35
        if closes and volumes:
            avg_dollar_volume = sum(max(0.0, c) * max(0.0, v) for c, v in zip(closes, volumes)) / max(1, len(closes))
            liquidity_score = max(0.05, min(1.0, avg_dollar_volume / 150_000_000.0))
        returns = []
        if len(closes) >= 2:
            for idx in range(1, len(closes)):
                prev = closes[idx - 1]
                curr = closes[idx]
                if prev:
                    returns.append((curr / prev) - 1.0)
        realized_vol = 0.0
        if len(returns) >= 5:
            try:
                realized_vol = statistics.pstdev(returns[-20:])
            except Exception:
                realized_vol = 0.0
        volatility_score = 1.0 - max(0.0, min(1.0, abs(realized_vol - 0.025) / 0.04))
        news_intensity_count = len(news_rows or [])
        catalyst_score = max(0.0, min(1.0, news_intensity_count / max(1, self._discovery_news_limit)))
        regime_alignment = max(0.0, min(1.0, float(regime_snapshot.confidence)))
        confidence = max(
            0.0,
            min(1.0, ((tech_conf * 0.25) + (ml_conf * 0.25) + (liquidity_score * 0.2) + (catalyst_score * 0.15) + (regime_alignment * 0.15))),
        )
        score = (
            (regime_alignment * 0.30)
            + (ml_prob_up * 0.20)
            + (sentiment_norm * 0.10)
            + (liquidity_score * 0.15)
            + (volatility_score * 0.10)
            + (catalyst_score * 0.15)
        )
        direction = regime_snapshot.direction if regime_snapshot.direction in {"long_bias", "short_bias"} else ("long_bias" if ml_prob_up >= 0.5 else "short_bias")
        top_headlines = [str(item.get("headline") or "").strip() for item in (news_rows or [])[:3] if str(item.get("headline") or "").strip()]
        math_summary = (
            f"score={score:.3f} from regime={regime_alignment:.3f}, ml={ml_prob_up:.3f}, "
            f"liquidity={liquidity_score:.3f}, vol={volatility_score:.3f}, catalyst={catalyst_score:.3f}."
        )
        opportunity = self._orchestrator.record_discovery_opportunity(
            {
                "run_id": self._autopilot_last_run_id or "autopilot-discovery",
                "agent_id": "world_scanner",
                "symbol": normalized,
                "asset_class": infer_asset_class(normalized),
                "strategy_family": "multi_signal_scout",
                "direction": direction,
                "score": score,
                "confidence": confidence,
                "horizon": "swing",
                "thesis": f"{normalized} ranked by multi-signal scout with {direction.replace('_', ' ')} bias and discovery confidence {confidence:.2f}.",
                "catalysts": list(dict.fromkeys([*top_headlines, str(technical.summary), str(sentiment.source), "ml_timeseries"])),
                "evidence": [
                    str(technical.summary),
                    str(ml.summary),
                    f"Sentiment score {round(_to_float(sentiment.sentiment_score, 0.0), 3)}",
                    math_summary,
                ],
                "ml": {
                    "directional_probability_up": round(ml_prob_up, 4),
                    "technical_confidence": round(tech_conf, 4),
                    "ml_confidence": round(ml_conf, 4),
                    "sentiment_normalized": round(sentiment_norm, 4),
                    "liquidity_score": round(liquidity_score, 4),
                    "volatility_score": round(volatility_score, 4),
                    "news_intensity_count": news_intensity_count,
                    "regime_alignment": round(regime_alignment, 4),
                    "market_regime": regime_snapshot.regime,
                    "regime_direction": regime_snapshot.direction,
                    "regime_edge": round(float(regime_snapshot.edge), 4),
                    "regime_notes": list(regime_snapshot.notes),
                    "math_summary": math_summary,
                },
                "metadata": {
                    "source": "autopilot_dynamic_universe",
                    "news_intensity_count": news_intensity_count,
                    "macro_risk_level": "elevated" if news_intensity_count >= self._discovery_news_limit else "normal",
                    "market_regime": regime_snapshot.regime,
                    "market_regime_confidence": round(float(regime_snapshot.confidence), 4),
                },
                "status": "candidate",
            }
        )
        return opportunity

    def _scheduled_market_brief_jobs(self) -> list[dict[str, Any]]:
        now_et = datetime.now(self._market_timezone)
        jobs: list[dict[str, Any]] = []
        weekday = now_et.weekday()
        market_date = now_et.date().isoformat()
        symbols = self._blog_market_report_symbols

        if self._blog_premarket_report_enabled and weekday < 5:
            trigger_time = now_et.replace(hour=9, minute=30, second=0, microsecond=0) - timedelta(
                minutes=self._blog_premarket_report_lead_minutes
            )
            schedule_key = f"premarket-{market_date}"
            if now_et >= trigger_time and not blog_service.has_scheduled_post(schedule_kind="premarket", schedule_key=schedule_key):
                jobs.append(
                    {
                        "kind": "premarket",
                        "schedule_key": schedule_key,
                        "market_date": market_date,
                        "symbols": symbols,
                        "command": (
                            "Write a dated premarket report using real overnight news, expected session pressure, "
                            "watchlist catalysts, and scenario-based speculation with explicit uncertainty."
                        ),
                    }
                )

        if self._blog_postmarket_report_enabled and weekday < 5:
            trigger_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0) + timedelta(
                minutes=self._blog_postmarket_report_delay_minutes
            )
            schedule_key = f"postmarket-{market_date}"
            if now_et >= trigger_time and not blog_service.has_scheduled_post(schedule_kind="postmarket", schedule_key=schedule_key):
                jobs.append(
                    {
                        "kind": "postmarket",
                        "schedule_key": schedule_key,
                        "market_date": market_date,
                        "symbols": symbols,
                        "command": (
                            "Write a dated postmarket report covering session winners/losers, closing narrative, "
                            "risk carryover into tomorrow, and what the price action likely means."
                        ),
                    }
                )

        if self._blog_weekahead_report_enabled and weekday == self._blog_weekahead_report_weekday:
            trigger_time = now_et.replace(
                hour=self._blog_weekahead_report_hour_et,
                minute=self._blog_weekahead_report_minute_et,
                second=0,
                microsecond=0,
            )
            iso_year, iso_week, _ = now_et.isocalendar()
            schedule_key = f"week-ahead-{iso_year}-W{iso_week:02d}"
            if now_et >= trigger_time and not blog_service.has_scheduled_post(schedule_kind="week_ahead", schedule_key=schedule_key):
                jobs.append(
                    {
                        "kind": "week_ahead",
                        "schedule_key": schedule_key,
                        "market_date": market_date,
                        "symbols": symbols,
                        "command": (
                            "Write a week-ahead report for serious operators: macro calendar, market structure, likely "
                            "crowding, cross-asset watchpoints, and where the fund should stay in cash if evidence is weak."
                        ),
                    }
                )

        return jobs

    def _enqueue_blog_editorial_cycle(self, run_id: str) -> dict[str, Any]:
        queued_task_ids: list[str] = []
        schedule_jobs = self._scheduled_market_brief_jobs()
        for job in schedule_jobs:
            task = self._task_bus.create_task(
                run_id=run_id,
                agent_id="editorial_coordinator",
                role="blog_writer",
                priority=9,
                payload={
                    "editorial_kind": job["kind"],
                    "schedule_key": job["schedule_key"],
                    "market_date": job["market_date"],
                    "symbols": list(job["symbols"]),
                    "symbol": str(job["symbols"][0]) if job["symbols"] else "SPY",
                    "command": job["command"],
                    "trigger_source": "scheduled_market_report",
                    "metadata": {
                        "scheduled": True,
                        "schedule_kind": job["kind"],
                        "schedule_key": job["schedule_key"],
                    },
                },
            )
            queued_task_ids.append(task.task_id)

        remaining = blog_service.daily_quota_remaining(self._blog_editorial_target_per_day)
        candidate_count = 0
        if remaining > 0:
            reports = self._orchestrator.list_recent_research_reports(limit=200)
            candidates = blog_service.select_editorial_candidates(
                reports=reports,
                min_confidence=self._blog_editorial_min_confidence,
                limit=remaining,
            )
            candidate_count = len(candidates)
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
            "candidate_count": candidate_count,
            "scheduled_market_reports": len(schedule_jobs),
            "remaining_quota": max(0, remaining - candidate_count),
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

    def _has_existing_pack_task(self, *, signal_pack_id: str, role: str) -> bool:
        for task in self._task_bus.list_tasks():
            if task.role != role or task.status not in {"queued", "running"}:
                continue
            if str(task.payload.get("signal_pack_id") or "").strip() == signal_pack_id:
                return True
        return False

    def _has_completed_pack_output(self, *, signal_pack_id: str, role: str) -> bool:
        with self._signal_pack_lock:
            state = self._signal_packs.get(signal_pack_id)
            if state is None:
                return False
            return role in state.outputs

    async def _process_task(self, role: WorkerRole, payload: dict[str, Any], *, run_id: str, task_id: str) -> dict[str, Any]:
        if data_integrity_guard.halted():
            return {
                "status": "blocked",
                "reason": data_integrity_guard.halt_reason() or "system_halted",
                "run_id": run_id,
                "task_id": task_id,
                "role": role,
            }
        if run_id in self._canceled_runs:
            return {
                "status": "blocked",
                "reason": str(self._canceled_runs[run_id].get("reason") or "run_canceled"),
                "run_id": run_id,
                "task_id": task_id,
                "role": role,
            }
        signal_pack_id = str(payload.get("signal_pack_id") or "").strip()
        if signal_pack_id and signal_pack_id in self._canceled_signal_packs:
            return {
                "status": "blocked",
                "reason": str(self._canceled_signal_packs[signal_pack_id].get("reason") or "signal_pack_canceled"),
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
            if signal_pack_id in self._canceled_signal_packs or run_id in self._canceled_runs:
                return {
                    "status": "blocked",
                    "report_id": report_id,
                    "signal_pack_id": signal_pack_id,
                    "reason": "signal_pack_canceled" if signal_pack_id in self._canceled_signal_packs else "run_canceled",
                    **dict(extra or {}),
                }
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
        if run_id in self._canceled_runs:
            return {"status": "blocked", "report_id": report_id, "reason": "run_canceled", **dict(extra or {})}
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
            if state.status == "canceled" or signal_pack_id in self._canceled_signal_packs:
                return {"status": "blocked", "reason": state.canceled_reason or "signal_pack_canceled"}

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
        asset_class = infer_asset_class(symbol, dict(payload.get("metadata") or {}).get("asset_class"))
        engine_signal = run_core_engine(symbol).to_dict()
        decision_scoring = build_decision_scoring_from_signal(
            symbol=symbol,
            asset_class=asset_class,
            engine_signal=engine_signal,
        )
        trader_metadata = {
            **dict(payload.get("metadata") or {}),
            "market_session": session,
            "deterministic_ml_signal": engine_signal,
            "decision_scoring": decision_scoring,
            "strategy_family": decision_scoring.get("strategy_family"),
            "signal_artifact_source": "fund_manager_snapshot",
            "signal_artifact_recorded_at": _utc_iso(),
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
                "metadata": trader_metadata,
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
        editorial_kind = str(payload.get("editorial_kind") or "").strip().lower()
        if editorial_kind:
            post = blog_service.publish_market_brief(
                schedule_kind=editorial_kind,
                schedule_key=str(payload.get("schedule_key") or "").strip(),
                market_date=str(payload.get("market_date") or "").strip(),
                run_id=run_id,
                symbols=payload.get("symbols") or self._blog_market_report_symbols,
                command=str(
                    payload.get("command")
                    or f"Write a dated {editorial_kind.replace('_', ' ')} market report with overnight news, scenarios, and risk watchpoints."
                ),
                trigger_source=str(payload.get("trigger_source") or "scheduled_market_report"),
            )
            return {
                "status": "completed",
                "published_count": 1,
                "post_ids": [str(post.get("id"))],
                "schedule_kind": editorial_kind,
                "schedule_key": str(payload.get("schedule_key") or ""),
            }

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
        swarm_wave_size=settings.AGENT_RUNTIME_SWARM_WAVE_SIZE,
        swarm_wave_spacing_seconds=settings.AGENT_RUNTIME_SWARM_WAVE_SPACING_SECONDS,
        swarm_max_active_packs=settings.AGENT_RUNTIME_SWARM_MAX_ACTIVE_PACKS,
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
        blog_market_report_scheduler_interval_seconds=settings.BLOG_MARKET_REPORT_SCHEDULER_INTERVAL_SECONDS,
        blog_premarket_report_enabled=settings.BLOG_PREMARKET_REPORT_ENABLED,
        blog_premarket_report_lead_minutes=settings.BLOG_PREMARKET_REPORT_LEAD_MINUTES,
        blog_postmarket_report_enabled=settings.BLOG_POSTMARKET_REPORT_ENABLED,
        blog_postmarket_report_delay_minutes=settings.BLOG_POSTMARKET_REPORT_DELAY_MINUTES,
        blog_weekahead_report_enabled=settings.BLOG_WEEKAHEAD_REPORT_ENABLED,
        blog_weekahead_report_weekday=_parse_weekday_name(settings.BLOG_WEEKAHEAD_REPORT_WEEKDAY),
        blog_weekahead_report_hour_et=settings.BLOG_WEEKAHEAD_REPORT_HOUR_ET,
        blog_weekahead_report_minute_et=settings.BLOG_WEEKAHEAD_REPORT_MINUTE_ET,
        blog_market_report_symbols=_parse_symbol_csv(settings.BLOG_MARKET_REPORT_SYMBOLS),
        ceo_digest_enabled=settings.CEO_DIGEST_ENABLED,
        ceo_digest_interval_seconds=settings.CEO_DIGEST_INTERVAL_SECONDS,
        discovery_min_score=settings.AGENT_RUNTIME_DISCOVERY_MIN_SCORE,
        discovery_min_confidence=settings.AGENT_RUNTIME_DISCOVERY_MIN_CONFIDENCE,
        discovery_news_limit=settings.AGENT_RUNTIME_DISCOVERY_NEWS_LIMIT,
    )


fund_agent_runtime = _build_runtime()
