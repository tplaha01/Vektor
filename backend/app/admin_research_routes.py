"""
Admin Console, Research, and Blog API Routes (live-backed).
"""

from __future__ import annotations

import asyncio
import math
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import monotonic
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.analytics import build_metrics_from_broker
from app.config import get_settings
from app.core.context import broker
from app.data.market_data import FEED
from app.fund.ai_role_adapter import ai_role_adapter
from app.fund.agent_runtime import fund_agent_runtime
from app.fund.audit_log import audit_log
from app.fund.blog_service import blog_service
from app.fund.ceo_service import vektor_ceo_service
from app.fund.contracts import ProvenanceRef, ResearchReport as ContractResearchReport
from app.fund.decision_ledger import decision_ledger
from app.fund.knowledge_graph import knowledge_graph
from app.fund.orchestrator import firm_orchestrator
from app.fund.performance_tracker import performance_tracker
from app.fund.runtime_guard import data_integrity_guard
from app.fund.sentiment_ingest import sentiment_ingest
from app.risk.engine import risk
from app.storage import db as storage_db


# ====================================================================
# Data Models
# ====================================================================


class MetricsSummary(BaseModel):
    total_equity: float
    equity_change: float
    account_equity: float = 0.0
    external_capital_flow_usd: float = 0.0
    baseline_equity: float = 0.0
    realized_pnl: float
    pnl_change: float
    unrealized_pnl: float
    current_drawdown: float
    drawdown_change: float
    max_drawdown_ytd: float
    max_drawdown_threshold: float
    active_positions: int
    win_rate: float
    win_rate_change: float
    sharpe_ratio: float
    sharpe_change: float


class AgentWorkerStatus(BaseModel):
    agent_id: str
    role: str
    status: str
    task_count: int
    success_rate: float
    last_heartbeat: datetime


class ActiveTask(BaseModel):
    task_id: str
    agent_id: str
    task_type: str
    status: str
    priority: int
    created_at: datetime


class PendingDecision(BaseModel):
    decision_id: str
    agent_id: str
    symbol: str
    side: str
    quantity: float
    confidence: float
    thesis: str
    sleeve: str
    created_at: datetime
    expires_at: datetime


class SleeveAllocation(BaseModel):
    sleeve_id: str
    total_capital: float
    allocated: float
    available: float
    active_positions: int
    pnl: float


class ResearchReport(BaseModel):
    report_id: str
    agent_id: str
    agent_role: str
    surface: str = "kb"
    run_id: Optional[str] = None
    title: str
    summary: str
    findings: List[str]
    asset_universe: List[str]
    confidence: float
    created_at: datetime
    published_at: datetime
    status: str
    views: Optional[int] = 0
    provider_used: Optional[str] = None
    model_used: Optional[str] = None
    ai_trace: dict = Field(default_factory=dict)
    provenance: dict


class ResearchReportCreateIn(BaseModel):
    run_id: Optional[str] = Field(default=None, min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    agent_role: Optional[str] = None
    surface: Literal["public", "kb"] = "public"
    title: str = Field(..., min_length=1, max_length=300)
    summary: str = Field(..., min_length=1, max_length=6000)
    findings: List[str] = Field(default_factory=list)
    asset_universe: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: str = Field(default="published")
    provenance: dict = Field(default_factory=dict)


class AuditEvent(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: str
    details: dict


class BlogGenerateIn(BaseModel):
    run_id: Optional[str] = None
    report_ids: List[str] = []
    symbol: Optional[str] = None
    command: str = "Write an expert blog post from latest Vektor research."
    priority: int = 7


class LineageRow(BaseModel):
    run_id: str
    started_at: datetime
    updated_at: datetime
    signal_pack_id: Optional[str] = None
    symbol: Optional[str] = None
    analyst_completed: int
    analyst_expected: int
    fund_manager_status: str
    trader_status: str
    decision_id: Optional[str] = None
    order_id: Optional[str] = None
    blocked_reasons: List[str] = Field(default_factory=list)
    blog_post_ids: List[str] = Field(default_factory=list)
    report_ids: List[str] = Field(default_factory=list)
    lineage_detail_path: Optional[str] = None
    decision_detail_path: Optional[str] = None
    audit_timeline_path: Optional[str] = None


class LineageDecisionDetail(BaseModel):
    decision_id: Optional[str] = None
    status: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    sleeve: Optional[str] = None
    thesis_id: Optional[str] = None
    risk_id: Optional[str] = None
    intent_id: Optional[str] = None


class LineageRunDetail(BaseModel):
    run_id: str
    summary: LineageRow
    decision: LineageDecisionDetail
    related_research_report_ids: List[str] = Field(default_factory=list)
    related_blog_post_ids: List[str] = Field(default_factory=list)
    related_blog_posts: List[dict] = Field(default_factory=list)
    audit_timeline: List[dict] = Field(default_factory=list)
    task_events: List[dict] = Field(default_factory=list)


class RuntimeControlIn(BaseModel):
    reason: str = Field(default="manual_admin_action", min_length=1, max_length=256)


class PaperBrokerCapitalIn(BaseModel):
    action: Literal["top_up", "set_cash", "reset"]
    amount_usd: Optional[float] = Field(default=None, gt=0)
    target_cash_usd: Optional[float] = Field(default=None, ge=0)
    clear_positions: bool = False
    clear_orders: bool = False
    reason: str = Field(default="manual_paper_capital_update", min_length=1, max_length=256)


class InceptionResetIn(BaseModel):
    starting_cash_usd: float = Field(default=100000.0, gt=0)
    reason: str = Field(default="clean_inception_reset", min_length=1, max_length=256)


class AutopilotKickIn(BaseModel):
    run_id: Optional[str] = Field(default=None, min_length=3, max_length=128)


class StrictModeIn(BaseModel):
    enabled: bool
    reason: str = Field(default="manual_strict_mode_update", min_length=1, max_length=256)


class DataIntegrityDrillIn(BaseModel):
    provider: str = Field(..., min_length=2, max_length=128)
    mode: Literal["provider", "fallback", "failed"]
    symbol: Optional[str] = Field(default=None, min_length=1, max_length=32)
    detail: Optional[str] = Field(default=None, max_length=512)
    reason: str = Field(default="manual_data_integrity_drill", min_length=1, max_length=256)


class FunctionalVerifyIn(BaseModel):
    run_id: Optional[str] = Field(default=None, min_length=3, max_length=128)
    symbol: str = Field(default="SPY", min_length=1, max_length=16)
    side: Literal["buy", "sell"] = "buy"
    quantity: float = Field(default=1.0, gt=0)
    timeout_seconds: int = Field(default=45, ge=5, le=180)


# ====================================================================
# Router Setup
# ====================================================================


router = APIRouter(prefix="/api/admin", tags=["admin"])
research_router = APIRouter(prefix="/api/research", tags=["research"])
blog_router = APIRouter(prefix="/api/blog", tags=["blog"])


# ====================================================================
# Helpers
# ====================================================================


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value or "").strip()
    if not text:
        return _utc_now()
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return _utc_now()


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _infer_agent_role(agent_id: str, fallback: str = "researcher") -> str:
    value = str(agent_id or "").lower()
    if "technical" in value:
        return "technical_analyst"
    if "fundamental" in value:
        return "fundamental_analyst"
    if "sentiment" in value:
        return "sentiment_analyst"
    if "ml" in value or "timeseries" in value:
        return "ml_timeseries_analyst"
    if "hedge" in value or "macro" in value:
        return "hedge_fund_researcher"
    if "insight" in value:
        return "insight_researcher"
    if "fund_manager" in value:
        return "fund_manager"
    if "risk" in value:
        return "risk_auditor"
    if "trader" in value:
        return "trader"
    return fallback


def _estimate_sharpe_from_recent_trades(analytics: dict[str, Any]) -> float:
    trades = analytics.get("recent_trades") or []
    returns: list[float] = []
    for item in trades:
        pnl = _safe_float(item.get("pnl"), 0.0)
        qty = abs(_safe_float(item.get("qty"), 0.0))
        buy_px = abs(_safe_float(item.get("buy"), 0.0))
        notional = qty * buy_px
        if notional <= 0:
            continue
        returns.append(pnl / notional)

    # Avoid unstable Sharpe estimates on tiny trade samples.
    if len(returns) < 20:
        return 0.0
    mean = statistics.mean(returns)
    stdev = statistics.pstdev(returns)
    if stdev <= 1e-6:
        return 0.0
    sharpe = (mean / stdev) * (252.0 ** 0.5)
    # Keep dashboard values readable and robust to noisy micro samples.
    return round(float(max(min(sharpe, 10.0), -10.0)), 2)


def _infer_baseline_equity(
    *,
    total_equity: float,
    realized_pnl: float,
    unrealized_pnl: float,
    fallback: float,
) -> float:
    """
    Infer baseline capital from current equity and PnL.
    This keeps performance % realistic after paper-capital top-ups/resets.
    """
    inferred = total_equity - (realized_pnl + unrealized_pnl)
    if not math.isfinite(inferred) or inferred <= 0:
        return fallback
    return inferred


def _metrics_summary_from_performance() -> MetricsSummary | None:
    performance = performance_tracker.summary()
    latest = performance.get("latest_snapshot") if isinstance(performance, dict) else None
    inception = performance.get("inception_snapshot") if isinstance(performance, dict) else None
    track_record = performance.get("track_record") if isinstance(performance, dict) else None
    if not isinstance(latest, dict) or not isinstance(track_record, dict):
        return None

    latest_positions = latest.get("positions") if isinstance(latest.get("positions"), list) else []
    latest_equity = _safe_float(latest.get("equity"), 0.0)
    baseline_equity = _safe_float(
        inception.get("equity") if isinstance(inception, dict) else None,
        latest_equity or _safe_float(getattr(risk, "INITIAL_EQUITY", 100000.0), 100000.0),
    )
    account_equity = _safe_float(broker.get_portfolio_value(lambda s: FEED.price(s)), latest_equity)
    external_capital_flow = account_equity - latest_equity
    risk_state = risk.status()
    dd = risk_state.get("drawdown_breaker") if isinstance(risk_state.get("drawdown_breaker"), dict) else {}

    return MetricsSummary(
        total_equity=round(latest_equity, 2),
        equity_change=round(_safe_float(track_record.get("total_return_pct"), 0.0), 2),
        account_equity=round(account_equity, 2),
        external_capital_flow_usd=round(external_capital_flow, 2),
        baseline_equity=round(baseline_equity, 2),
        realized_pnl=round(_safe_float(latest.get("realized_pnl"), 0.0), 2),
        pnl_change=0.0,
        unrealized_pnl=round(_safe_float(latest.get("unrealized_pnl"), 0.0), 2),
        current_drawdown=round(_safe_float(dd.get("current_drawdown"), 0.0) * 100.0, 2),
        drawdown_change=0.0,
        max_drawdown_ytd=round(_safe_float(track_record.get("max_drawdown_pct"), 0.0), 2),
        max_drawdown_threshold=round(_safe_float(dd.get("max_drawdown_threshold"), 0.10) * 100.0, 2),
        active_positions=len(latest_positions),
        win_rate=round(_safe_float(latest.get("win_rate"), 0.0), 2),
        win_rate_change=0.0,
        sharpe_ratio=round(_safe_float(track_record.get("sharpe_ratio"), 0.0), 2),
        sharpe_change=0.0,
    )


def _normalize_provenance(raw_provenance: Any) -> dict:
    refs = raw_provenance if isinstance(raw_provenance, list) else []
    data_sources: list[str] = []
    decision_ids: list[str] = []
    thesis_id: str | None = None
    policy_gates_applied: list[str] = []

    for ref in refs:
        if not isinstance(ref, dict):
            continue
        source_type = str(ref.get("source_type") or "").strip().lower()
        source_id = str(ref.get("source_id") or "").strip()
        if not source_id:
            continue
        data_sources.append(f"{source_type}:{source_id}" if source_type else source_id)
        if source_type == "thesis" and thesis_id is None:
            thesis_id = source_id
        if source_type in {"execution", "decision"}:
            decision_ids.append(source_id)
        if source_type == "risk":
            policy_gates_applied.append(source_id)

    return {
        "data_sources": data_sources,
        "thesis_id": thesis_id,
        "decision_ids": decision_ids,
        "policy_gates_applied": policy_gates_applied,
    }


def _resolve_report_ai_trace(
    *,
    report_id: str,
    run_id: str | None,
    agent_id: str,
    agent_role: str,
    task_history_cache: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    run_key = str(run_id or "").strip()
    if not run_key:
        return {}

    if task_history_cache is not None and run_key in task_history_cache:
        history = task_history_cache[run_key]
    else:
        history = firm_orchestrator.list_task_history(limit=1600, run_id=run_key)
        if task_history_cache is not None:
            task_history_cache[run_key] = history
    best_trace: dict[str, Any] = {}
    normalized_agent_id = str(agent_id or "").strip().lower()
    normalized_role = str(agent_role or "").strip().lower()

    for row in history:
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        trace = details.get("ai_role_adapter") if isinstance(details.get("ai_role_adapter"), dict) else {}
        candidate_report_id = str(
            details.get("report_id")
            or payload.get("report_id")
            or payload.get("research_id")
            or ""
        ).strip()
        if candidate_report_id != report_id or not trace:
            continue

        row_agent_id = str(row.get("agent_id") or "").strip().lower()
        row_role = str(row.get("role") or "").strip().lower()
        role_matches = row_role == normalized_role or row_agent_id == normalized_agent_id
        if role_matches:
            return dict(trace)
        if not best_trace:
            best_trace = dict(trace)

    return best_trace


def _infer_report_surface(
    *,
    row: dict[str, Any],
    agent_id: str,
    agent_role: str,
    title: str,
    summary: str,
) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    explicit = str(metadata.get("surface") or row.get("surface") or "").strip().lower()
    if explicit in {"public", "kb"}:
        return explicit

    title_l = title.lower()
    summary_l = summary.lower()
    agent_id_l = str(agent_id or "").strip().lower()
    agent_role_l = str(agent_role or "").strip().lower()

    if agent_id_l in {"signal_committee_agent", "fund_manager_agent", "trader_agent", "risk_auditor_agent"}:
        return "kb"
    if agent_role_l in ANALYST_ROLE_SET or agent_role_l in {"fund_manager", "trader", "risk_auditor"}:
        return "kb"
    if any(keyword in title_l or keyword in summary_l for keyword in ("proposal", "discovery", "case study", "research paper")):
        return "public"
    if agent_role_l == "researcher" and "signal" not in title_l and "brief" not in title_l:
        return "public"
    return "kb"


def _map_live_report(
    row: dict[str, Any],
    *,
    task_history_cache: dict[str, list[dict[str, Any]]] | None = None,
) -> ResearchReport:
    report_id = str(row.get("report_id") or uuid.uuid4().hex)
    run_id = str(row.get("run_id") or "").strip() or None
    created_at = _to_datetime(row.get("created_at"))
    summary = str(row.get("summary") or "")
    findings = row.get("findings") if isinstance(row.get("findings"), list) else [summary]
    assets = row.get("asset_universe") if isinstance(row.get("asset_universe"), list) else []
    agent_id = str(row.get("agent_id") or "research_agent")
    agent_role = _infer_agent_role(agent_id)
    title = str(row.get("title") or f"Research Report {report_id[:8]}")
    provenance = _normalize_provenance(row.get("provenance"))
    ai_trace = _resolve_report_ai_trace(
        report_id=report_id,
        run_id=run_id,
        agent_id=agent_id,
        agent_role=agent_role,
        task_history_cache=task_history_cache,
    )
    surface = _infer_report_surface(
        row=row,
        agent_id=agent_id,
        agent_role=agent_role,
        title=title,
        summary=summary,
    )

    return ResearchReport(
        report_id=report_id,
        agent_id=agent_id,
        agent_role=agent_role,
        surface=surface,
        run_id=run_id,
        title=title,
        summary=summary,
        findings=[str(item) for item in findings if str(item).strip()] or [summary],
        asset_universe=[str(asset).upper() for asset in assets if str(asset).strip()],
        confidence=_safe_float(row.get("confidence"), 0.0),
        created_at=created_at,
        published_at=created_at,
        status="published",
        views=_safe_int(row.get("views"), 0),
        provider_used=str(ai_trace.get("provider") or "").strip() or None,
        model_used=str(ai_trace.get("model") or "").strip() or None,
        ai_trace=ai_trace,
        provenance=provenance,
    )


def _decision_context(decision_id: str) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for event in reversed(decision_ledger.list_events(limit=-1)):
        if str(event.get("decision_id")) != decision_id:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        for key in ("symbol", "side", "quantity", "conviction", "statement", "sleeve"):
            if key in payload and key not in context:
                context[key] = payload[key]
        if all(key in context for key in ("symbol", "side", "quantity")):
            break
    return context


ANALYST_ROLE_SET = {
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_timeseries_analyst",
    "insight_researcher",
    "hedge_fund_researcher",
}


def _normalize_binary_status(value: str, *, default: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in {"healthy", "provider"}:
        return "Healthy" if cleaned == "healthy" else "Provider"
    if cleaned in {"degraded", "fallback"}:
        return "Degraded" if cleaned == "degraded" else "Fallback"
    return default


def _halt_recovery_checklist(
    *,
    halt_reason: str | None,
    runtime_started: bool,
    strict_real_data_only: bool,
) -> list[str]:
    reason = str(halt_reason or "").strip().lower()
    checklist: list[str] = [
        "Confirm upstream providers are healthy and returning live data (Alpaca market data + news source).",
        "Verify `REAL_DATA_STRICT_MODE=true` and paper-only execution mode are still enforced.",
        "Clear halt from Admin: Settings -> Runtime Controls -> Clear Halt.",
        "Resume runtime, then kick autopilot once to validate full orchestration recovery.",
    ]

    if not runtime_started:
        checklist.insert(0, "Start agent runtime first; halted systems cannot recover while runtime is paused.")

    if "missing_alpaca_api_key" in reason or "alpaca" in reason:
        checklist.insert(1, "Set valid `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`, then restart backend.")
    if "missing_finnhub_key" in reason or "finnhub" in reason:
        checklist.insert(1, "Set valid `FINNHUB_KEY` for news ingestion resilience, then restart backend.")
    if "adapter_error" in reason or "ai_role_adapter" in reason:
        checklist.insert(1, "Check AI role adapter routing, provider quota state, and failover health before resuming swarms.")
    if "openclaw" in reason:
        checklist.insert(1, "Restart OpenClaw gateway and verify Discord channel connectivity before issuing control commands.")

    if not strict_real_data_only:
        checklist.insert(
            0,
            "Strict real-data mode is disabled. Re-enable it before clearing halt to avoid unsafe fallback execution.",
        )

    # Preserve order, remove duplicates.
    deduped: list[str] = []
    seen: set[str] = set()
    for item in checklist:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _record_runtime_control_event(
    *,
    action: str,
    status: str,
    reason: str | None,
    payload: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    control_run_id = str(run_id or f"run-admin-control-{uuid.uuid4().hex[:12]}")
    control_payload = {
        "action": str(action or "unknown").strip().lower(),
        "status": str(status or "unknown").strip().lower(),
        "reason": str(reason or "").strip() or None,
        "actor": "api.admin",
        **dict(payload or {}),
    }
    audit_log.record(
        "runtime.control",
        {
            "run_id": control_run_id,
            "agent_id": "api.admin",
            **control_payload,
        },
    )
    return knowledge_graph.ingest(
        source="runtime",
        event_type=f"runtime.control.{control_payload['action']}",
        run_id=control_run_id,
        agent_id="api.admin",
        payload=control_payload,
    )


def _collect_functional_snapshot(history: list[dict[str, Any]], *, default_symbol: str) -> dict[str, Any]:
    expected_roles: set[str] = set(ANALYST_ROLE_SET)
    completed_roles: set[str] = set()
    fund_manager_status = "unknown"
    trader_status = "unknown"
    trader_terminal = False
    decision_id: str | None = None
    order_id: str | None = None
    blocked_reasons: list[str] = []
    analyst_failed_roles: dict[str, str] = {}
    report_ids: set[str] = set()
    blog_post_ids: set[str] = set()
    symbol = str(default_symbol or "").upper().strip() or None

    for row in history:
        role = str(row.get("role") or "").strip()
        status = str(row.get("status") or "").strip().lower()
        event = str(row.get("event") or "").strip().lower()
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}

        for source in (payload, details):
            pack_roles = source.get("signal_pack_roles")
            if isinstance(pack_roles, list):
                expected_roles = {
                    str(item).strip().lower()
                    for item in pack_roles
                    if str(item).strip().lower() in ANALYST_ROLE_SET
                } or expected_roles
            report_id = str(source.get("report_id") or "").strip()
            if report_id:
                report_ids.add(report_id)
            for report_id_item in (source.get("report_ids") if isinstance(source.get("report_ids"), list) else []):
                rid = str(report_id_item).strip()
                if rid:
                    report_ids.add(rid)
            for post_id in (source.get("post_ids") if isinstance(source.get("post_ids"), list) else []):
                pid = str(post_id).strip()
                if pid:
                    blog_post_ids.add(pid)
            maybe_symbol = str(source.get("symbol") or "").strip().upper()
            if maybe_symbol and not symbol:
                symbol = maybe_symbol

        if role in ANALYST_ROLE_SET and event == "status_update" and status == "completed":
            completed_roles.add(role)
        if role in ANALYST_ROLE_SET and event == "status_update" and status in {"failed", "blocked"}:
            reason = str(details.get("reason") or details.get("error") or "").strip()
            if not reason:
                reasons = details.get("reasons") if isinstance(details.get("reasons"), list) else []
                if reasons:
                    reason = str(reasons[0]).strip()
            analyst_failed_roles[role] = reason or status

        if role == "fund_manager" and event == "status_update":
            fund_manager_status = status or fund_manager_status

        if role == "trader" and event == "status_update" and status in {"completed", "blocked", "failed"}:
            trader_status = status
            trader_terminal = True
            maybe_decision = str(details.get("decision_id") or "").strip()
            if maybe_decision:
                decision_id = maybe_decision
            maybe_order = details.get("order_id")
            if maybe_order is None:
                execution = details.get("execution") if isinstance(details.get("execution"), dict) else {}
                order = execution.get("order") if isinstance(execution.get("order"), dict) else {}
                maybe_order = order.get("id")
            if maybe_order is not None:
                order_id = str(maybe_order)
            reasons = details.get("reasons") if isinstance(details.get("reasons"), list) else []
            if not reasons and details.get("reason"):
                reasons = [details.get("reason")]
            blocked_reasons = [str(item) for item in reasons if str(item).strip()]

    return {
        "symbol": symbol or str(default_symbol or "").upper().strip() or None,
        "analyst_expected": len(expected_roles),
        "analyst_completed": len(completed_roles),
        "analyst_missing_roles": sorted(role for role in expected_roles if role not in completed_roles),
        "analyst_failed_roles": dict(sorted(analyst_failed_roles.items(), key=lambda item: item[0])),
        "fund_manager_status": fund_manager_status,
        "trader_status": trader_status,
        "trader_terminal": trader_terminal,
        "terminal_failure": bool(analyst_failed_roles),
        "decision_id": decision_id,
        "order_id": order_id,
        "blocked_reasons": blocked_reasons,
        "report_ids": sorted(report_ids),
        "blog_post_ids": sorted(blog_post_ids),
    }


# ====================================================================
# Admin Endpoints (live-backed)
# ====================================================================


@router.get("/metrics/summary", response_model=MetricsSummary)
async def get_metrics_summary():
    performance_metrics = _metrics_summary_from_performance()
    if performance_metrics is not None:
        return performance_metrics

    positions = broker.list_positions(lambda s: FEED.price(s))
    analytics = build_metrics_from_broker(broker)
    equity = risk.update_equity(positions, analytics.get("realized_pnl", 0.0))
    risk_state = risk.status()
    dd = risk_state.get("drawdown_breaker") or {}

    baseline_default = _safe_float(getattr(risk, "INITIAL_EQUITY", 100000.0), 100000.0)
    account_equity = _safe_float(equity, baseline_default)
    unrealized = sum(_safe_float(p.get("unrealized_pnl")) for p in positions)
    realized = _safe_float(analytics.get("realized_pnl"), 0.0)
    strategy_equity = baseline_default + realized + unrealized
    external_capital_flow = account_equity - strategy_equity
    flow_ratio = abs(external_capital_flow) / max(baseline_default, 1.0)
    # If significant external capital movement happened, show strategy-adjusted equity.
    total_equity = strategy_equity if flow_ratio >= 0.05 else account_equity
    baseline_equity = baseline_default

    max_drawdown_abs = abs(_safe_float(analytics.get("max_drawdown"), 0.0))
    max_drawdown_pct = (max_drawdown_abs / baseline_equity) * 100.0 if baseline_equity > 0 else 0.0

    return MetricsSummary(
        total_equity=round(total_equity, 2),
        equity_change=round(((total_equity - baseline_equity) / baseline_equity) * 100.0, 2),
        account_equity=round(account_equity, 2),
        external_capital_flow_usd=round(external_capital_flow, 2),
        baseline_equity=round(baseline_equity, 2),
        realized_pnl=round(realized, 2),
        pnl_change=0.0,
        unrealized_pnl=round(unrealized, 2),
        current_drawdown=round(_safe_float(dd.get("current_drawdown"), 0.0) * 100.0, 2),
        drawdown_change=0.0,
        max_drawdown_ytd=round(max_drawdown_pct, 2),
        max_drawdown_threshold=round(_safe_float(dd.get("max_drawdown_threshold"), 0.10) * 100.0, 2),
        active_positions=len(positions),
        win_rate=round(_safe_float(analytics.get("win_rate"), 0.0), 2),
        win_rate_change=0.0,
        sharpe_ratio=_estimate_sharpe_from_recent_trades(analytics),
        sharpe_change=0.0,
    )


@router.get("/system/status-badges", response_model=dict)
async def get_system_status_badges():
    settings = get_settings()
    runtime = fund_agent_runtime.status()
    workers = runtime.get("workers") if isinstance(runtime.get("workers"), list) else []
    data_integrity = runtime.get("data_integrity")
    if not isinstance(data_integrity, dict):
        data_integrity = data_integrity_guard.status()

    halted = bool(data_integrity.get("halted"))
    halt_reason = str(data_integrity.get("halt_reason") or "").strip() or None
    halted_at = data_integrity.get("halted_at")

    runtime_started = bool(runtime.get("started"))
    worker_errors = [
        str(worker.get("last_error") or "").strip()
        for worker in workers
        if str(worker.get("last_error") or "").strip()
    ]
    orchestration_status = "Healthy"
    orchestration_reason = "all_runtime_workers_operational"
    if not runtime_started:
        orchestration_status = "Degraded"
        orchestration_reason = "agent_runtime_not_started"
    elif halted:
        orchestration_status = "Degraded"
        orchestration_reason = halt_reason or "system_halted"
    elif worker_errors:
        orchestration_status = "Degraded"
        orchestration_reason = worker_errors[0]

    raw_data_source_status = _normalize_binary_status(
        str(data_integrity.get("data_source_status") or "Provider"),
        default="Provider",
    )
    if halted:
        data_source_status = "Fallback"
    else:
        data_source_status = "Provider" if raw_data_source_status == "Provider" else "Fallback"
    if orchestration_status == "Healthy" and data_source_status != "Provider":
        orchestration_status = "Degraded"
        orchestration_reason = "data_source_fallback_detected"

    broker_mode = str(settings.BROKER or "").strip().lower()
    execution_mode_status = "Paper Only" if broker_mode == "paper" else "Degraded"
    execution_mode_reason = "paper_mode_confirmed" if broker_mode == "paper" else "live_mode_forbidden"

    worker_by_role = {
        str(worker.get("role") or "").strip(): worker
        for worker in workers
        if str(worker.get("role") or "").strip()
    }
    ai_health = runtime.get("ai_role_adapter")
    if not isinstance(ai_health, dict):
        ai_health = ai_role_adapter.health()
    ai_enabled = bool(ai_health.get("enabled"))
    ai_provider = str(ai_health.get("provider") or "unknown")
    ai_mode = str(ai_health.get("mode") or "single_provider")
    role_models = ai_health.get("role_models") if isinstance(ai_health.get("role_models"), dict) else {}
    default_model = str(ai_health.get("default_model") or "").strip()
    adapter_last_error = str(ai_health.get("last_error") or "").strip()
    provider_runtime = ai_health.get("providers") if isinstance(ai_health.get("providers"), dict) else {}
    role_runtime = ai_health.get("role_runtime") if isinstance(ai_health.get("role_runtime"), dict) else {}

    role_health: list[dict[str, Any]] = []
    for role in sorted(ANALYST_ROLE_SET):
        worker = worker_by_role.get(role, {})
        worker_last_error = str(worker.get("last_error") or "").strip()
        worker_running = bool(worker.get("running"))
        runtime_state = role_runtime.get(role) if isinstance(role_runtime.get(role), dict) else {}
        model = str(runtime_state.get("last_model") or role_models.get(role) or default_model or "").strip()
        role_provider = str(runtime_state.get("last_provider") or ai_provider or "unknown").strip()
        route = runtime_state.get("route") if isinstance(runtime_state.get("route"), list) else []
        fallback_used = bool(runtime_state.get("fallback_used"))
        failover_count = _safe_int(runtime_state.get("failover_count"), 0)

        degraded_reasons: list[str] = []
        if halted:
            degraded_reasons.append(halt_reason or "system_halted")
        if not ai_enabled:
            degraded_reasons.append("ai_role_adapter_disabled")
        if not model:
            degraded_reasons.append("model_unconfigured")
        if worker_last_error:
            degraded_reasons.append(f"worker_error:{worker_last_error}")
        if not worker_running and runtime_started and not worker_last_error:
            degraded_reasons.append("worker_not_running")

        status = "Degraded" if degraded_reasons else "Healthy"
        role_health.append(
            {
                "role": role,
                "status": status,
                "provider": role_provider,
                "model": model or None,
                "reason": degraded_reasons[0] if degraded_reasons else "ok",
                "route": route,
                "fallback_used": fallback_used,
                "failover_count": failover_count,
            }
        )

    llm_overall = "Degraded" if any(item["status"] == "Degraded" for item in role_health) else "Healthy"
    if llm_overall == "Healthy" and adapter_last_error:
        llm_overall = "Healthy"

    halt_message = None
    if halted:
        halt_message = (
            "System halted: strict real-data mode detected provider fallback/failure. "
            "Signal generation, task orchestration, and trade execution are blocked until resolved."
        )
    allocation_status = firm_orchestrator.allocation_policy_status()
    discovery_rows = firm_orchestrator.list_discovery_opportunities(limit=8)
    active_contexts = runtime.get("active_contexts") if isinstance(runtime.get("active_contexts"), list) else []
    recovery_checklist = _halt_recovery_checklist(
        halt_reason=halt_reason,
        runtime_started=runtime_started,
        strict_real_data_only=bool(data_integrity.get("strict_real_data_only")),
    )

    return {
        "timestamp": _utc_now().isoformat(),
        "orchestration": {
            "label": "Orchestration",
            "status": orchestration_status,
            "reason": orchestration_reason,
        },
        "data_source": {
            "label": "Data Source",
            "status": data_source_status,
            "strict_real_data_only": bool(data_integrity.get("strict_real_data_only")),
            "providers": data_integrity.get("providers") if isinstance(data_integrity.get("providers"), list) else [],
            "last_event": data_integrity.get("last_event") if isinstance(data_integrity.get("last_event"), dict) else None,
        },
        "execution_mode": {
            "label": "Execution Mode",
            "status": execution_mode_status,
            "broker": broker_mode or "unknown",
            "reason": execution_mode_reason,
        },
        "llm_agent_health": {
            "label": "LLM Agent Health",
            "status": llm_overall,
            "by_role": role_health,
            "adapter_warning": adapter_last_error or None,
            "mode": ai_mode,
            "default_route": ai_health.get("default_route") if isinstance(ai_health.get("default_route"), list) else [],
            "role_routes": ai_health.get("role_routes") if isinstance(ai_health.get("role_routes"), dict) else {},
            "providers": provider_runtime,
            "gateway": ai_health.get("gateway") if isinstance(ai_health.get("gateway"), dict) else {},
        },
        "allocation_policy": allocation_status,
        "discovery": {
            "count": len(discovery_rows),
            "top": discovery_rows,
        },
        "swarm_snapshot": {
            "active_contexts": active_contexts,
            "signal_packs": runtime.get("signal_packs") if isinstance(runtime.get("signal_packs"), list) else [],
        },
        "halt": {
            "halted": halted,
            "reason": halt_reason,
            "halted_at": halted_at,
            "message": halt_message,
            "recovery_checklist": recovery_checklist,
        },
    }


@router.get("/system/runtime/control", response_model=dict)
async def get_runtime_control_status():
    runtime = fund_agent_runtime.status()
    halt = runtime.get("data_integrity") if isinstance(runtime.get("data_integrity"), dict) else data_integrity_guard.status()
    halt_reason = str(halt.get("halt_reason") or "").strip() or None
    runtime_started = bool(runtime.get("started"))
    recovery_checklist = _halt_recovery_checklist(
        halt_reason=halt_reason,
        runtime_started=runtime_started,
        strict_real_data_only=bool(halt.get("strict_real_data_only")),
    )
    return {
        "runtime_started": runtime_started,
        "active_task_count": len(firm_orchestrator.list_active_tasks()),
        "autopilot": runtime.get("autopilot", {}),
        "halted": bool(halt.get("halted")),
        "halt_reason": halt_reason,
        "halted_at": halt.get("halted_at"),
        "strict_real_data_only": bool(halt.get("strict_real_data_only")),
        "recovery_checklist": recovery_checklist,
    }


@router.get("/system/ops/panel", response_model=dict)
async def get_ops_panel(limit: int = Query(20, ge=1, le=200)):
    status_badges = await get_system_status_badges()
    runtime_control = await get_runtime_control_status()
    lineage = await get_recent_lineage(limit=limit)
    return {
        "status_badges": status_badges,
        "runtime_control": runtime_control,
        "recent_lineage": lineage,
    }


@router.post("/system/data-integrity/strict-mode", response_model=dict)
async def set_strict_mode(body: StrictModeIn):
    result = data_integrity_guard.set_strict_mode(body.enabled, reason=body.reason)
    runtime = fund_agent_runtime.status()
    response = {
        "ok": True,
        "action": "strict_mode_updated",
        "strict_real_data_only": bool(result.get("strict_real_data_only")),
        "strict_real_data_only_previous": bool(result.get("strict_real_data_only_previous")),
        "halt_auto_cleared": bool(result.get("halt_auto_cleared")),
        "runtime_started": bool(runtime.get("started")),
        "status": result.get("status"),
    }
    _record_runtime_control_event(
        action="set_strict_mode",
        status="updated",
        reason=body.reason,
        payload={
            "strict_real_data_only": response["strict_real_data_only"],
            "strict_real_data_only_previous": response["strict_real_data_only_previous"],
            "halt_auto_cleared": response["halt_auto_cleared"],
        },
    )
    return response


@router.post("/system/data-integrity/drill", response_model=dict)
async def run_data_integrity_drill(body: DataIntegrityDrillIn):
    normalized_symbol = str(body.symbol or "").strip().upper() or None
    normalized_detail = str(body.detail or body.reason).strip()[:512] or None
    data_integrity_guard.record_provider_event(
        provider=body.provider,
        mode=body.mode,
        symbol=normalized_symbol,
        detail=normalized_detail,
    )
    status = data_integrity_guard.status()
    response = {
        "ok": True,
        "action": "data_integrity_drill_recorded",
        "provider": body.provider,
        "mode": body.mode,
        "symbol": normalized_symbol,
        "detail": normalized_detail,
        "halted": bool(status.get("halted")),
        "halt_reason": status.get("halt_reason"),
        "status": status,
    }
    _record_runtime_control_event(
        action="data_integrity_drill",
        status="recorded",
        reason=body.reason,
        payload={
            "provider": body.provider,
            "mode": body.mode,
            "symbol": normalized_symbol,
            "detail": normalized_detail,
            "halted": response["halted"],
            "halt_reason": response["halt_reason"],
        },
    )
    return response


@router.get("/system/control-history", response_model=dict)
async def get_runtime_control_history(limit: int = Query(30, ge=1, le=200)):
    events = knowledge_graph.list_events(limit=max(limit * 8, 200), namespace="runtime", source="runtime")
    rows: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        if not event_type.startswith("runtime.control."):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        rows.append(
            {
                "event_id": str(event.get("event_id") or ""),
                "timestamp": event.get("occurred_at"),
                "run_id": event.get("run_id"),
                "event_type": event_type,
                "action": str(payload.get("action") or event_type.split(".")[-1]).strip().lower(),
                "status": str(payload.get("status") or "unknown").strip().lower(),
                "reason": str(payload.get("reason") or "").strip() or None,
                "actor": str(payload.get("actor") or event.get("agent_id") or "api.admin"),
                "payload": payload,
            }
        )
        if len(rows) >= limit:
            break
    return {"rows": rows, "total": len(rows), "limit": limit}


@router.post("/system/runtime/pause", response_model=dict)
async def pause_runtime(body: RuntimeControlIn):
    was_started = fund_agent_runtime.is_started()
    if was_started:
        await fund_agent_runtime.stop()
    runtime = fund_agent_runtime.status()
    response = {
        "ok": True,
        "action": "paused" if was_started else "already_paused",
        "reason": body.reason,
        "runtime_started": bool(runtime.get("started")),
        "active_task_count": len(firm_orchestrator.list_active_tasks()),
    }
    _record_runtime_control_event(
        action="pause",
        status=str(response["action"]),
        reason=body.reason,
        payload={"runtime_started": response["runtime_started"]},
    )
    return response


@router.post("/system/runtime/resume", response_model=dict)
async def resume_runtime(body: RuntimeControlIn):
    if data_integrity_guard.halted():
        _record_runtime_control_event(
            action="resume",
            status="rejected",
            reason=data_integrity_guard.halt_reason() or "strict_real_data_halt",
            payload={"blocked": True},
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error": "system_halted",
                "reason": data_integrity_guard.halt_reason() or "strict_real_data_halt",
                "message": "Clear halt first, then resume runtime.",
            },
        )
    already_started = fund_agent_runtime.is_started()
    if not already_started:
        await fund_agent_runtime.start()
    runtime = fund_agent_runtime.status()
    response = {
        "ok": True,
        "action": "resumed" if not already_started else "already_running",
        "reason": body.reason,
        "runtime_started": bool(runtime.get("started")),
        "active_task_count": len(firm_orchestrator.list_active_tasks()),
    }
    _record_runtime_control_event(
        action="resume",
        status=str(response["action"]),
        reason=body.reason,
        payload={"runtime_started": response["runtime_started"]},
    )
    return response


@router.post("/system/halt/clear", response_model=dict)
async def clear_system_halt(body: RuntimeControlIn):
    result = data_integrity_guard.clear_halt(reason=body.reason)
    runtime = fund_agent_runtime.status()
    response = {
        "ok": True,
        "action": "halt_cleared",
        "runtime_started": bool(runtime.get("started")),
        **result,
    }
    _record_runtime_control_event(
        action="clear_halt",
        status="halt_cleared",
        reason=body.reason,
        payload={"previous_halt_reason": result.get("previous_halt_reason")},
    )
    return response


@router.post("/system/paper-broker/capital", response_model=dict)
async def update_paper_broker_capital(body: PaperBrokerCapitalIn):
    settings = get_settings()
    broker_mode = str(settings.BROKER or "").strip().lower()
    if broker_mode != "paper":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "paper_only_endpoint",
                "message": "Paper broker capital controls are available only in paper mode.",
            },
        )

    before_cash = float(getattr(broker, "cash", 0.0))
    before_positions = len(getattr(broker, "positions", {}) or {})
    before_orders = len(getattr(broker, "order_history", []) or [])

    action = body.action
    if action == "top_up":
        if body.amount_usd is None:
            raise HTTPException(status_code=400, detail="amount_usd_required_for_top_up")
        broker.cash = float(broker.cash) + float(body.amount_usd)
    elif action == "set_cash":
        if body.target_cash_usd is None:
            raise HTTPException(status_code=400, detail="target_cash_usd_required_for_set_cash")
        broker.cash = float(body.target_cash_usd)
    elif action == "reset":
        target = float(body.target_cash_usd) if body.target_cash_usd is not None else 100000.0
        broker.cash = max(0.0, target)
        if body.clear_positions:
            broker.positions = {}
        if body.clear_orders:
            broker.order_history = []
            broker._order_counter = 0  # noqa: SLF001

    persist_fn = getattr(broker, "persist_state", None)
    if callable(persist_fn):
        persist_fn()

    after_cash = float(getattr(broker, "cash", 0.0))
    after_positions = len(getattr(broker, "positions", {}) or {})
    after_orders = len(getattr(broker, "order_history", []) or [])

    response = {
        "ok": True,
        "action": f"paper_broker_{action}",
        "mode": "paper",
        "reason": body.reason,
        "before": {
            "cash_usd": round(before_cash, 2),
            "positions_count": before_positions,
            "orders_count": before_orders,
        },
        "after": {
            "cash_usd": round(after_cash, 2),
            "positions_count": after_positions,
            "orders_count": after_orders,
        },
    }
    _record_runtime_control_event(
        action="paper_broker_capital",
        status="updated",
        reason=body.reason,
        payload={
            "request_action": action,
            "before_cash_usd": round(before_cash, 2),
            "after_cash_usd": round(after_cash, 2),
            "clear_positions": bool(body.clear_positions),
            "clear_orders": bool(body.clear_orders),
        },
    )
    return response


@router.post("/system/inception/reset", response_model=dict)
async def reset_clean_inception(body: InceptionResetIn):
    settings = get_settings()
    broker_mode = str(settings.BROKER or "").strip().lower()
    if broker_mode != "paper":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "paper_only_endpoint",
                "message": "Clean inception reset is available only in paper mode.",
            },
        )

    before_cash = float(getattr(broker, "cash", 0.0))
    before_positions = len(getattr(broker, "positions", {}) or {})
    before_orders = len(getattr(broker, "order_history", []) or [])
    before_performance = performance_tracker.summary()

    broker_reset = storage_db.clear_paper_broker_state(body.starting_cash_usd)
    broker.cash = float(body.starting_cash_usd)
    broker.positions = {}
    broker.order_history = []
    broker._order_counter = 0  # noqa: SLF001

    risk_state = risk.reset(starting_equity=body.starting_cash_usd)
    performance_reset = performance_tracker.reset()
    inception_snapshot = await performance_tracker.capture_snapshot(
        snapshot_kind="manual",
        reason=body.reason,
    )

    response = {
        "ok": True,
        "action": "clean_inception_reset",
        "mode": "paper",
        "reason": body.reason,
        "before": {
            "cash_usd": round(before_cash, 2),
            "positions_count": before_positions,
            "orders_count": before_orders,
            "performance_snapshot_count": int(before_performance.get("snapshot_count") or 0),
        },
        "after": {
            "cash_usd": round(float(body.starting_cash_usd), 2),
            "positions_count": 0,
            "orders_count": 0,
            "performance_snapshot_count": 1,
            "inception_snapshot_id": inception_snapshot.get("snapshot_id"),
        },
        "broker_reset": broker_reset,
        "performance_reset": performance_reset,
        "risk_state": risk_state,
    }
    _record_runtime_control_event(
        action="clean_inception_reset",
        status="completed",
        reason=body.reason,
        payload={
            "starting_cash_usd": round(float(body.starting_cash_usd), 2),
            "deleted_orders": broker_reset.get("deleted_orders", 0),
            "deleted_positions": broker_reset.get("deleted_positions", 0),
            "deleted_cash_snapshots": broker_reset.get("deleted_cash_snapshots", 0),
            "deleted_performance_snapshots": performance_reset.get("deleted_snapshots", 0),
            "deleted_benchmark_baselines": performance_reset.get("deleted_baselines", 0),
            "inception_snapshot_id": inception_snapshot.get("snapshot_id"),
        },
    )
    return response


@router.post("/system/autopilot/kick", response_model=dict)
async def kick_autopilot(body: AutopilotKickIn, background_tasks: BackgroundTasks):
    if not fund_agent_runtime.is_started():
        result = {"accepted": False, "reason": "runtime_not_started"}
    elif data_integrity_guard.halted():
        result = {"accepted": False, "reason": data_integrity_guard.halt_reason() or "system_halted"}
    else:
        run_id = str(body.run_id or f"run-autopilot-{uuid.uuid4().hex[:12]}")
        background_tasks.add_task(fund_agent_runtime.kick_autopilot, run_id)
        result = {
            "accepted": True,
            "manual": True,
            "queued": True,
            "run_id": run_id,
            "message": "Autopilot cycle scheduled in background.",
        }
    if not result.get("accepted"):
        _record_runtime_control_event(
            action="kick_autopilot",
            status="rejected",
            reason=str(result.get("reason") or "autopilot_rejected"),
            payload={"accepted": False, "run_id": body.run_id},
            run_id=body.run_id,
        )
        raise HTTPException(status_code=400, detail=result.get("reason", "autopilot_rejected"))
    response = {"ok": True, **result}
    _record_runtime_control_event(
        action="kick_autopilot",
        status="accepted",
        reason=None,
        payload={"accepted": True},
        run_id=str(result.get("run_id") or body.run_id or ""),
    )
    return response


@router.post("/system/functional/verify", response_model=dict)
async def verify_functional_pipeline(body: FunctionalVerifyIn):
    if data_integrity_guard.halted():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "system_halted",
                "reason": data_integrity_guard.halt_reason() or "strict_real_data_halt",
                "message": "Clear system halt before running functional verification.",
            },
        )

    if not fund_agent_runtime.is_started():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "runtime_not_started",
                "message": "Agent runtime must be started before functional verification.",
            },
        )

    symbol = str(body.symbol or "SPY").strip().upper()
    run_id = str(body.run_id or f"run-functional-verify-{uuid.uuid4().hex[:12]}")
    started = monotonic()

    queued = fund_agent_runtime.enqueue_signal_swarm(
        run_id=run_id,
        symbol=symbol,
        agent_id="api.admin",
        command=f"functional verification for {symbol}",
        payload={
            "symbol": symbol,
            "side": body.side,
            "quantity": float(body.quantity),
            "sleeve": "tactical",
            "verification": True,
            "metadata": {"verification_source": "api.admin.system.functional.verify"},
        },
        priority=9,
    )
    if str(queued.get("status") or "").lower() == "blocked":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "verification_enqueue_blocked",
                "reason": queued.get("reason"),
                "run_id": run_id,
            },
        )

    deadline = monotonic() + float(body.timeout_seconds)
    history: list[dict[str, Any]] = []
    snapshot = _collect_functional_snapshot(history, default_symbol=symbol)
    while monotonic() < deadline:
        history = firm_orchestrator.list_task_history(limit=5000, run_id=run_id)
        snapshot = _collect_functional_snapshot(history, default_symbol=symbol)
        if snapshot.get("trader_terminal") or snapshot.get("terminal_failure"):
            break
        await asyncio.sleep(0.5)

    timed_out = not bool(snapshot.get("trader_terminal") or snapshot.get("terminal_failure"))
    verification_status = "timeout"
    if not timed_out:
        if snapshot.get("terminal_failure"):
            verification_status = "failed"
        else:
            trader_status = str(snapshot.get("trader_status") or "").lower()
            if trader_status == "completed":
                verification_status = "passed"
            elif trader_status == "blocked":
                verification_status = "passed_with_risk_block"
            else:
                verification_status = "failed"

    order_id = str(snapshot.get("order_id") or "").strip() or None
    decision_id = str(snapshot.get("decision_id") or "").strip() or None
    audit_timeline: list[dict[str, Any]] = []
    if order_id:
        audit_timeline = firm_orchestrator.audit_timeline_for_order(order_id)[-100:]
    elif decision_id:
        for row in decision_ledger.list_events(limit=-1):
            if str(row.get("decision_id") or "") != decision_id:
                continue
            audit_timeline.append(
                {
                    "source": "decision_ledger",
                    "event_id": row.get("event_id"),
                    "event_type": row.get("event_type"),
                    "timestamp": row.get("ts"),
                    "payload": row.get("payload") if isinstance(row.get("payload"), dict) else {},
                }
            )
        audit_timeline.sort(key=lambda item: item.get("timestamp") or "")

    elapsed_ms = int((monotonic() - started) * 1000)
    return {
        "ok": verification_status in {"passed", "passed_with_risk_block"},
        "status": verification_status,
        "run_id": run_id,
        "elapsed_ms": elapsed_ms,
        "queued": queued,
        "pipeline": snapshot,
        "task_event_count": len(history),
        "audit_timeline": audit_timeline,
        "lineage_detail_path": f"/api/admin/lineage/run/{run_id}",
        "data_integrity": data_integrity_guard.status(),
    }


@router.get("/agents/workers/status", response_model=dict)
async def get_agents_status():
    runtime = fund_agent_runtime.status()
    workers = runtime.get("workers") or []
    mapped: list[AgentWorkerStatus] = []

    for worker in workers:
        role = str(worker.get("role") or "unknown")
        completed = _safe_int(worker.get("completed_count"))
        failed = _safe_int(worker.get("failed_count"))
        blocked = _safe_int(worker.get("blocked_count"))
        total = completed + failed + blocked
        success_rate = (completed / total) if total > 0 else 1.0
        status = "error" if worker.get("last_error") else ("running" if worker.get("running") else "idle")

        mapped.append(
            AgentWorkerStatus(
                agent_id=str(worker.get("last_task_id") or f"{role}_agent"),
                role=role,
                status=status,
                task_count=total,
                success_rate=round(success_rate, 4),
                last_heartbeat=_to_datetime(worker.get("last_heartbeat_at")),
            )
        )

    return {
        "workers": [item.model_dump(mode="json") for item in mapped],
        "runtime_started": bool(runtime.get("started")),
        "autopilot": runtime.get("autopilot", {}),
    }


@router.get("/agents/tasks/active", response_model=dict)
async def get_active_tasks():
    rows = firm_orchestrator.list_active_tasks()
    tasks = [
        ActiveTask(
            task_id=str(item.get("task_id") or uuid.uuid4().hex),
            agent_id=str(item.get("agent_id") or "unknown_agent"),
            task_type=str(item.get("role") or item.get("task_type") or "task"),
            status=str(item.get("status") or "queued"),
            priority=_safe_int(item.get("priority"), 5),
            created_at=_to_datetime(item.get("created_at")),
        ).model_dump(mode="json")
        for item in rows
    ]
    return {"tasks": tasks}


@router.get("/decisions/pending", response_model=dict)
async def get_pending_decisions():
    rows = firm_orchestrator.list_pending_decisions()
    decisions: list[dict[str, Any]] = []

    for row in rows:
        decision_id = str(row.get("decision_id") or "")
        created_at = _to_datetime(row.get("created_at"))
        ctx = _decision_context(decision_id)

        decisions.append(
            PendingDecision(
                decision_id=decision_id,
                agent_id=str(row.get("agent_id") or "fund_manager_agent"),
                symbol=str(ctx.get("symbol") or "N/A"),
                side=str(ctx.get("side") or "buy"),
                quantity=_safe_float(ctx.get("quantity"), 0.0),
                confidence=_safe_float(ctx.get("conviction"), 0.5),
                thesis=str(ctx.get("statement") or f"Decision {decision_id}"),
                sleeve=str(row.get("sleeve") or ctx.get("sleeve") or "tactical"),
                created_at=created_at,
                expires_at=created_at + timedelta(minutes=30),
            ).model_dump(mode="json")
        )

    return {"decisions": decisions}


@router.get("/decisions/{decision_id}", response_model=dict)
async def get_decision_detail(decision_id: str):
    key = str(decision_id or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="invalid_decision_id")

    decision = next((item for item in decision_ledger.list_decisions() if item.decision_id == key), None)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision_not_found")

    context = _decision_context(key)
    timeline = [row for row in decision_ledger.list_events(limit=-1) if str(row.get("decision_id") or "") == key]
    timeline.sort(key=lambda row: str(row.get("ts") or ""))

    order_id = None
    blocked_reasons: list[str] = []
    for row in reversed(timeline):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if order_id is None and payload.get("order_id") is not None:
            order_id = str(payload.get("order_id"))
        reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
        if not reasons and payload.get("reason"):
            reasons = [payload.get("reason")]
        if reasons:
            blocked_reasons = [str(item) for item in reasons if str(item).strip()]
            break

    audit_timeline_path = f"/api/admin/audit/orders/{order_id}/timeline" if order_id else None
    pending_approval = firm_orchestrator.find_pending_trade_approval(decision_id=key)
    approval_payload = dict(pending_approval.get("payload") or {}) if isinstance(pending_approval, dict) else {}
    discovery_snapshot = firm_orchestrator.latest_discovery_opportunity(
        run_id=decision.run_id,
        symbol=(context or {}).get("symbol") or "",
    )
    return {
        "decision_id": decision.decision_id,
        "run_id": decision.run_id,
        "agent_id": decision.agent_id,
        "status": decision.status,
        "sleeve": decision.sleeve.value,
        "thesis_id": decision.thesis_id,
        "risk_id": decision.risk_id,
        "intent_id": decision.intent_id,
        "context": context,
        "blocked_reasons": blocked_reasons,
        "order_id": order_id,
        "approval_request_id": pending_approval.get("request_id") if pending_approval else None,
        "risk_gate": approval_payload.get("risk_gate"),
        "decision_scoring": {
            "score": discovery_snapshot.get("score"),
            "confidence": discovery_snapshot.get("confidence"),
            "direction": discovery_snapshot.get("direction"),
            "asset_class": discovery_snapshot.get("asset_class"),
            "strategy_family": discovery_snapshot.get("strategy_family"),
            "horizon": discovery_snapshot.get("horizon"),
            "math_summary": (discovery_snapshot.get("ml") or {}).get("math_summary"),
            "metrics": dict((discovery_snapshot.get("ml") or {})),
        } if discovery_snapshot else None,
        "audit_timeline_path": audit_timeline_path,
        "lineage_detail_path": f"/api/admin/lineage/run/{decision.run_id}",
        "events": timeline,
    }


@router.post("/decisions/{decision_id}/approve")
async def approve_decision(decision_id: str):
    decision = next((item for item in decision_ledger.list_decisions() if item.decision_id == decision_id), None)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision_not_found")
    request = firm_orchestrator.find_pending_trade_approval(decision_id=decision_id)
    if request is None:
        raise HTTPException(status_code=404, detail="approval_request_not_found")
    return firm_orchestrator.approve_request(str(request.get("request_id") or ""), reviewed_by="api.admin")


@router.post("/decisions/{decision_id}/reject")
async def reject_decision(decision_id: str):
    decision = next((item for item in decision_ledger.list_decisions() if item.decision_id == decision_id), None)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision_not_found")
    request = firm_orchestrator.find_pending_trade_approval(decision_id=decision_id)
    if request is None:
        raise HTTPException(status_code=404, detail="approval_request_not_found")
    return firm_orchestrator.reject_request(str(request.get("request_id") or ""), reviewed_by="api.admin")


@router.get("/sleeves/budgets", response_model=dict)
async def get_sleeve_budgets():
    payload = firm_orchestrator.sleeve_budget_status()
    runs = payload.get("runs") or []
    sleeves: list[dict[str, Any]] = []

    if runs:
        latest = runs[-1]
        rows = latest.get("sleeves") or {}
        for sleeve_id, row in rows.items():
            allocated = _safe_float((row or {}).get("allocated_usd"), 0.0)
            used = _safe_float((row or {}).get("used_usd"), 0.0)
            remaining = _safe_float((row or {}).get("remaining_usd"), max(0.0, allocated - used))
            sleeves.append(
                SleeveAllocation(
                    sleeve_id=str(sleeve_id),
                    total_capital=round(allocated, 2),
                    allocated=round(used, 2),
                    available=round(remaining, 2),
                    active_positions=0,
                    pnl=0.0,
                ).model_dump(mode="json")
            )
    else:
        defaults = payload.get("configured_defaults") or {}
        total = _safe_float(defaults.get("total_capital_usd"), 0.0)
        reserve = _safe_float(defaults.get("reserve_cash_usd"), 0.0)
        deployable = max(0.0, total - reserve)
        weights = defaults.get("weights") if isinstance(defaults.get("weights"), dict) else {}
        for sleeve_id in ("long_term", "recurring", "tactical"):
            cap = deployable * _safe_float(weights.get(sleeve_id), 0.0)
            sleeves.append(
                SleeveAllocation(
                    sleeve_id=sleeve_id,
                    total_capital=round(cap, 2),
                    allocated=0.0,
                    available=round(cap, 2),
                    active_positions=0,
                    pnl=0.0,
                ).model_dump(mode="json")
            )

    return {"sleeves": sleeves}


@router.get("/allocation/policy", response_model=dict)
async def get_allocation_policy(run_id: str | None = Query(default=None, min_length=3, max_length=128)):
    return firm_orchestrator.allocation_policy_status(run_id=run_id)


@router.post("/allocation/policy", response_model=dict)
async def update_allocation_policy(body: dict[str, Any]):
    run_id = str(body.get("run_id") or "").strip()
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id_required")
    agent_id = str(body.get("agent_id") or "ceo").strip() or "ceo"
    return firm_orchestrator.set_allocation_policy(
        run_id=run_id,
        agent_id=agent_id,
        total_capital_usd=body.get("total_capital_usd"),
        reserve_cash_usd=body.get("reserve_cash_usd"),
        asset_weights=body.get("asset_weights") if isinstance(body.get("asset_weights"), dict) else None,
        sleeve_weights=body.get("sleeve_weights") if isinstance(body.get("sleeve_weights"), dict) else None,
        constraints=body.get("constraints") if isinstance(body.get("constraints"), dict) else None,
        metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else None,
    )


@router.get("/discovery/opportunities", response_model=dict)
async def get_discovery_opportunities(
    limit: int = Query(default=100, ge=1, le=2000),
    run_id: str | None = Query(default=None, min_length=3, max_length=128),
    status: str | None = Query(default=None, min_length=2, max_length=64),
    asset_class: str | None = Query(default=None, min_length=2, max_length=64),
):
    rows = firm_orchestrator.list_discovery_opportunities(
        limit=limit,
        run_id=run_id,
        status=status,
        asset_class=asset_class,
    )
    return {"opportunities": rows}


@router.get("/operator/crm", response_model=dict)
async def get_operator_crm(
    task_limit: int = Query(default=60, ge=10, le=500),
    opportunity_limit: int = Query(default=40, ge=5, le=500),
):
    runtime = fund_agent_runtime.status()
    return {
        "status_badges": await get_system_status_badges(),
        "metrics": await get_metrics_summary(),
        "runtime_control": await get_runtime_control_status(),
        "allocation_policy": firm_orchestrator.allocation_policy_status(),
        "discovery": {
            "opportunities": firm_orchestrator.list_discovery_opportunities(limit=opportunity_limit),
        },
        "swarm_snapshot": {
            "active_contexts": runtime.get("active_contexts") if isinstance(runtime.get("active_contexts"), list) else [],
            "signal_packs": runtime.get("signal_packs") if isinstance(runtime.get("signal_packs"), list) else [],
            "workers": runtime.get("workers") if isinstance(runtime.get("workers"), list) else [],
        },
        "tasks": {
            "active": firm_orchestrator.list_active_tasks(),
            "history": firm_orchestrator.list_task_history(limit=task_limit),
        },
        "decisions": {
            "pending": firm_orchestrator.list_pending_decisions(),
            "blocked": firm_orchestrator.list_blocked_trades(limit=task_limit),
        },
    }


@router.get("/audit/orders/{order_id}/timeline", response_model=dict)
async def get_order_audit_timeline(order_id: str):
    rows = firm_orchestrator.audit_timeline_for_order(order_id)
    events = [
        AuditEvent(
            event_id=str(item.get("event_id") or uuid.uuid4().hex),
            timestamp=_to_datetime(item.get("timestamp")),
            event_type=str(item.get("event_type") or "event"),
            details=item.get("payload") if isinstance(item.get("payload"), dict) else {},
        ).model_dump(mode="json")
        for item in rows
    ]
    return {"events": events}


@router.get("/lineage/recent", response_model=dict)
async def get_recent_lineage(limit: int = Query(20, ge=1, le=200)):
    # Pull a large-enough recent window and aggregate signal_pack -> decision -> order chains by run_id.
    history = firm_orchestrator.list_task_history(limit=max(1200, limit * 120))
    by_run: dict[str, dict[str, Any]] = {}

    for row in history:
        run_id = str(row.get("run_id") or "").strip()
        if not run_id:
            continue
        ts = _to_datetime(row.get("ts"))
        role = str(row.get("role") or "").strip()
        status = str(row.get("status") or "").strip()
        event = str(row.get("event") or "").strip()
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}

        state = by_run.setdefault(
            run_id,
            {
                "run_id": run_id,
                "started_at": ts,
                "updated_at": ts,
                "signal_pack_id": None,
                "symbol": None,
                "analyst_completed_roles": set(),
                "analyst_expected_roles": set(),
                "fund_manager_status": "unknown",
                "trader_status": "unknown",
                "decision_id": None,
                "order_id": None,
                "blocked_reasons": [],
                "blog_post_ids": [],
                "report_ids": set(),
            },
        )

        if ts < state["started_at"]:
            state["started_at"] = ts
        if ts > state["updated_at"]:
            state["updated_at"] = ts

        if role in ANALYST_ROLE_SET:
            state["analyst_expected_roles"].add(role)
            if event == "status_update" and status == "completed":
                state["analyst_completed_roles"].add(role)

        for source in (details, payload):
            signal_pack_id = str(source.get("signal_pack_id") or "").strip()
            if signal_pack_id and not state["signal_pack_id"]:
                state["signal_pack_id"] = signal_pack_id
            symbol = str(source.get("symbol") or "").strip().upper()
            if symbol and not state["symbol"]:
                state["symbol"] = symbol
            execution = source.get("execution") if isinstance(source.get("execution"), dict) else {}
            intent = execution.get("intent") if isinstance(execution.get("intent"), dict) else {}
            nested_symbol = str(intent.get("symbol") or "").strip().upper()
            if nested_symbol and not state["symbol"]:
                state["symbol"] = nested_symbol
            report_id = str(source.get("report_id") or "").strip()
            if report_id:
                state["report_ids"].add(report_id)
            report_ids = source.get("report_ids") if isinstance(source.get("report_ids"), list) else []
            for report_id_item in report_ids:
                rid = str(report_id_item).strip()
                if rid:
                    state["report_ids"].add(rid)
            composite_report_id = str(source.get("composite_report_id") or "").strip()
            if composite_report_id:
                state["report_ids"].add(composite_report_id)

        if role == "fund_manager" and event == "status_update":
            state["fund_manager_status"] = status or state["fund_manager_status"]

        if role == "trader" and event == "status_update" and status in {"completed", "blocked", "failed"}:
            trader_status = str(details.get("status") or "").strip().lower() or status
            state["trader_status"] = trader_status
            decision_id = str(details.get("decision_id") or "").strip()
            if decision_id:
                state["decision_id"] = decision_id
            order_id = details.get("order_id")
            if order_id is None:
                execution = details.get("execution") if isinstance(details.get("execution"), dict) else {}
                order = execution.get("order") if isinstance(execution.get("order"), dict) else {}
                order_id = order.get("id")
            if order_id is not None:
                state["order_id"] = str(order_id)
            reasons = details.get("reasons") if isinstance(details.get("reasons"), list) else []
            if not reasons:
                detail_reason = details.get("reason")
                if detail_reason:
                    reasons = [detail_reason]
            if not reasons:
                execution = details.get("execution") if isinstance(details.get("execution"), dict) else {}
                execution_reason = execution.get("reason")
                if execution_reason:
                    reasons = [execution_reason]
            if reasons:
                state["blocked_reasons"] = [str(reason) for reason in reasons if str(reason).strip()]

        if role == "blog_writer" and event == "status_update":
            post_ids = details.get("post_ids") if isinstance(details.get("post_ids"), list) else []
            for post_id in post_ids:
                pid = str(post_id).strip()
                if pid and pid not in state["blog_post_ids"]:
                    state["blog_post_ids"].append(pid)

    rows: list[dict[str, Any]] = []
    for _, state in by_run.items():
        expected_roles = sorted(state["analyst_expected_roles"] or [])
        completed_roles = sorted(state["analyst_completed_roles"] or [])
        rows.append(
            LineageRow(
                run_id=state["run_id"],
                started_at=state["started_at"],
                updated_at=state["updated_at"],
                signal_pack_id=state["signal_pack_id"],
                symbol=state["symbol"],
                analyst_completed=len(completed_roles),
                analyst_expected=len(expected_roles) if expected_roles else len(ANALYST_ROLE_SET),
                fund_manager_status=state["fund_manager_status"],
                trader_status=state["trader_status"],
                decision_id=state["decision_id"],
                order_id=state["order_id"],
                blocked_reasons=list(state["blocked_reasons"]),
                blog_post_ids=list(state["blog_post_ids"]),
                report_ids=sorted(state["report_ids"]),
                lineage_detail_path=f"/api/admin/lineage/run/{state['run_id']}",
                decision_detail_path=(
                    f"/api/admin/decisions/{state['decision_id']}"
                    if state["decision_id"]
                    else None
                ),
                audit_timeline_path=(
                    f"/api/admin/audit/orders/{state['order_id']}/timeline"
                    if state["order_id"]
                    else None
                ),
            ).model_dump(mode="json")
        )

    rows.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"rows": rows[:limit], "total": len(rows), "limit": limit}


@router.get("/lineage/run/{run_id}", response_model=LineageRunDetail)
async def get_lineage_run_detail(run_id: str, limit: int = Query(300, ge=20, le=2000)):
    run_key = str(run_id or "").strip()
    if not run_key:
        raise HTTPException(status_code=400, detail="invalid_run_id")

    history = firm_orchestrator.list_task_history(limit=max(1000, limit), run_id=run_key)
    if not history:
        raise HTTPException(status_code=404, detail="run_not_found")

    summary_state: dict[str, Any] = {
        "run_id": run_key,
        "started_at": _to_datetime(history[0].get("ts")),
        "updated_at": _to_datetime(history[-1].get("ts")),
        "signal_pack_id": None,
        "symbol": None,
        "analyst_completed_roles": set(),
        "analyst_expected_roles": set(),
        "fund_manager_status": "unknown",
        "trader_status": "unknown",
        "decision_id": None,
        "order_id": None,
        "blocked_reasons": [],
        "blog_post_ids": [],
    }

    related_report_ids: set[str] = set()
    related_blog_ids: set[str] = set()
    fallback_decision_id: str | None = summary_state.get("decision_id")

    normalized_events: list[dict[str, Any]] = []
    for row in history:
        ts = _to_datetime(row.get("ts"))
        if ts < summary_state["started_at"]:
            summary_state["started_at"] = ts
        if ts > summary_state["updated_at"]:
            summary_state["updated_at"] = ts

        role = str(row.get("role") or "").strip()
        status = str(row.get("status") or "").strip()
        event = str(row.get("event") or "").strip()
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}

        if role in ANALYST_ROLE_SET:
            summary_state["analyst_expected_roles"].add(role)
            if event == "status_update" and status == "completed":
                summary_state["analyst_completed_roles"].add(role)

        for source in (details, payload):
            signal_pack_id = str(source.get("signal_pack_id") or "").strip()
            if signal_pack_id and not summary_state["signal_pack_id"]:
                summary_state["signal_pack_id"] = signal_pack_id
            symbol = str(source.get("symbol") or "").strip().upper()
            if symbol and not summary_state["symbol"]:
                summary_state["symbol"] = symbol
            execution = source.get("execution") if isinstance(source.get("execution"), dict) else {}
            intent = execution.get("intent") if isinstance(execution.get("intent"), dict) else {}
            nested_symbol = str(intent.get("symbol") or "").strip().upper()
            if nested_symbol and not summary_state["symbol"]:
                summary_state["symbol"] = nested_symbol

        if role == "fund_manager" and event == "status_update":
            summary_state["fund_manager_status"] = status or summary_state["fund_manager_status"]

        if role == "trader" and event == "status_update" and status in {"completed", "blocked", "failed"}:
            trader_status = str(details.get("status") or "").strip().lower() or status
            summary_state["trader_status"] = trader_status
            decision_id = str(details.get("decision_id") or "").strip()
            if decision_id:
                summary_state["decision_id"] = decision_id
            order_id = details.get("order_id")
            if order_id is None:
                execution = details.get("execution") if isinstance(details.get("execution"), dict) else {}
                order = execution.get("order") if isinstance(execution.get("order"), dict) else {}
                order_id = order.get("id")
            if order_id is not None:
                summary_state["order_id"] = str(order_id)
            reasons = details.get("reasons") if isinstance(details.get("reasons"), list) else []
            if not reasons and details.get("reason"):
                reasons = [details.get("reason")]
            if not reasons:
                execution = details.get("execution") if isinstance(details.get("execution"), dict) else {}
                if execution.get("reason"):
                    reasons = [execution.get("reason")]
            if reasons:
                summary_state["blocked_reasons"] = [str(reason) for reason in reasons if str(reason).strip()]

        if role == "blog_writer" and event == "status_update":
            post_ids = details.get("post_ids") if isinstance(details.get("post_ids"), list) else []
            for post_id in post_ids:
                pid = str(post_id).strip()
                if pid and pid not in summary_state["blog_post_ids"]:
                    summary_state["blog_post_ids"].append(pid)

        if details.get("report_id"):
            related_report_ids.add(str(details.get("report_id")))
        for report_id in (details.get("report_ids") if isinstance(details.get("report_ids"), list) else []):
            rid = str(report_id).strip()
            if rid:
                related_report_ids.add(rid)
        for report_id in (payload.get("report_ids") if isinstance(payload.get("report_ids"), list) else []):
            rid = str(report_id).strip()
            if rid:
                related_report_ids.add(rid)
        if details.get("composite_report_id"):
            related_report_ids.add(str(details.get("composite_report_id")))
        for post_id in (details.get("post_ids") if isinstance(details.get("post_ids"), list) else []):
            pid = str(post_id).strip()
            if pid:
                related_blog_ids.add(pid)
        decision_id = str(details.get("decision_id") or "").strip()
        if decision_id:
            fallback_decision_id = decision_id

        normalized_events.append(
            {
                "task_id": str(row.get("task_id") or ""),
                "role": role,
                "agent_id": str(row.get("agent_id") or ""),
                "status": status,
                "event": event,
                "timestamp": ts.isoformat(),
                "details": details,
                "payload": payload,
            }
        )

    normalized_events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    limited_events = normalized_events[:limit]

    summary = LineageRow(
        run_id=summary_state["run_id"],
        started_at=summary_state["started_at"],
        updated_at=summary_state["updated_at"],
        signal_pack_id=summary_state["signal_pack_id"],
        symbol=summary_state["symbol"],
        analyst_completed=len(sorted(summary_state["analyst_completed_roles"])),
        analyst_expected=(
            len(sorted(summary_state["analyst_expected_roles"]))
            if summary_state["analyst_expected_roles"]
            else len(ANALYST_ROLE_SET)
        ),
        fund_manager_status=summary_state["fund_manager_status"],
        trader_status=summary_state["trader_status"],
        decision_id=summary_state["decision_id"],
        order_id=summary_state["order_id"],
        blocked_reasons=list(summary_state["blocked_reasons"]),
        blog_post_ids=list(summary_state["blog_post_ids"]),
        report_ids=sorted(related_report_ids),
        lineage_detail_path=f"/api/admin/lineage/run/{run_key}",
        decision_detail_path=(
            f"/api/admin/decisions/{summary_state['decision_id']}"
            if summary_state["decision_id"]
            else None
        ),
        audit_timeline_path=(
            f"/api/admin/audit/orders/{summary_state['order_id']}/timeline"
            if summary_state["order_id"]
            else None
        ),
    )

    decision_id = str(summary.decision_id or fallback_decision_id or "").strip() or None
    decision_detail = LineageDecisionDetail(decision_id=decision_id)
    if decision_id:
        decision = next((item for item in decision_ledger.list_decisions() if item.decision_id == decision_id), None)
        if decision is not None:
            decision_detail = LineageDecisionDetail(
                decision_id=decision.decision_id,
                status=decision.status,
                run_id=decision.run_id,
                agent_id=decision.agent_id,
                sleeve=decision.sleeve.value if decision.sleeve else None,
                thesis_id=decision.thesis_id,
                risk_id=decision.risk_id,
                intent_id=decision.intent_id,
            )

    order_id = summary.order_id
    audit_timeline: list[dict[str, Any]] = []
    if order_id:
        audit_timeline = firm_orchestrator.audit_timeline_for_order(str(order_id))
    elif decision_id:
        for row in decision_ledger.list_events(limit=-1):
            if str(row.get("decision_id") or "") != decision_id:
                continue
            audit_timeline.append(
                {
                    "source": "decision_ledger",
                    "event_id": row.get("event_id"),
                    "event_type": row.get("event_type"),
                    "timestamp": row.get("ts"),
                    "payload": row.get("payload") if isinstance(row.get("payload"), dict) else {},
                }
            )
    audit_timeline.sort(key=lambda item: item.get("timestamp") or "")

    related_blog_posts: list[dict[str, Any]] = []
    for blog_id in sorted(related_blog_ids):
        try:
            post = storage_db.load_blog_post(blog_id)
        except Exception:
            post = None
        if not post:
            continue
        related_blog_posts.append(
            {
                "id": post.get("id"),
                "slug": post.get("slug"),
                "title": post.get("title"),
                "published_at": post.get("published_at"),
            }
        )

    return LineageRunDetail(
        run_id=run_key,
        summary=summary,
        decision=decision_detail,
        related_research_report_ids=sorted(related_report_ids),
        related_blog_post_ids=sorted(related_blog_ids),
        related_blog_posts=related_blog_posts,
        audit_timeline=audit_timeline[-200:],
        task_events=limited_events,
    )


# ====================================================================
# Research Endpoints (live-backed)
# ====================================================================


@research_router.get("/reports", response_model=dict)
async def get_research_reports(
    status: Optional[str] = Query(None, description="Filter by status: draft, published, archived"),
    agent_role: Optional[str] = Query(None, description="Filter by agent role"),
    asset: Optional[str] = Query(None, description="Filter by asset symbol"),
    surface: Optional[str] = Query(None, description="Filter by surface: public, kb, all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if status and status.lower() not in {"published", "all"}:
        return {"reports": [], "total": 0, "limit": limit, "offset": offset}

    raw = firm_orchestrator.list_recent_research_reports(limit=max(limit + offset, limit), symbol=asset)
    task_history_cache: dict[str, list[dict[str, Any]]] = {}
    mapped = [_map_live_report(item, task_history_cache=task_history_cache).model_dump(mode="json") for item in raw]

    if surface and surface.lower() not in {"all"}:
        surface_l = surface.lower()
        mapped = [item for item in mapped if str(item.get("surface") or "").lower() == surface_l]

    if agent_role:
        agent_role_l = agent_role.lower()
        mapped = [item for item in mapped if str(item.get("agent_role") or "").lower() == agent_role_l]

    total = len(mapped)
    paged = mapped[offset : offset + limit]
    return {"reports": paged, "total": total, "limit": limit, "offset": offset}


@research_router.get("/reports/{report_id}", response_model=ResearchReport)
async def get_research_report_detail(report_id: str):
    report = firm_orchestrator.get_research_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="research_report_not_found")
    return _map_live_report(report)


@research_router.post("/reports")
async def create_research_report(report: ResearchReportCreateIn):
    run_id = report.run_id or f"run-research-api-{uuid.uuid4().hex[:10]}"
    findings = tuple(report.findings or [report.summary])
    refs = report.provenance.get("refs") if isinstance(report.provenance, dict) else None
    provenance_refs: list[ProvenanceRef] = []
    if isinstance(refs, list):
        for item in refs:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("source_type") or "research").strip().lower()
            if source_type not in {"data", "research", "thesis", "risk", "execution", "allocation", "sentiment"}:
                source_type = "research"
            source_id = str(item.get("source_id") or "").strip()
            if not source_id:
                continue
            provenance_refs.append(ProvenanceRef(source_type=source_type, source_id=source_id))

    contract = ContractResearchReport(
        run_id=run_id,
        agent_id=report.agent_id,
        asset_universe=tuple(str(asset).upper() for asset in report.asset_universe if str(asset).strip()),
        summary=report.summary,
        findings=findings,
        confidence=Decimal(str(report.confidence)),
        provenance=tuple(provenance_refs),
    )
    saved = firm_orchestrator.submit_research(contract)
    return {
        "status": "created",
        "report_id": saved["report_id"],
        "run_id": run_id,
        "published_at": saved.get("created_at") or _utc_now().isoformat(),
    }


@research_router.get("/sentiment/current", response_model=dict)
async def get_current_sentiment():
    rows = sentiment_ingest.list_recent(limit=500)
    by_symbol: dict[str, list[Any]] = {}
    for row in rows:
        by_symbol.setdefault(row.asset, []).append(row)

    snapshots: list[dict[str, Any]] = []
    for symbol, items in by_symbol.items():
        items.sort(key=lambda x: x.created_at, reverse=True)
        latest = items[0]
        sample = items[:20]
        avg_score = sum(item.sentiment_score for item in sample) / max(1, len(sample))
        avg_conf = sum(item.provenance.confidence for item in sample) / max(1, len(sample))
        snapshots.append(
            {
                "symbol": symbol,
                "sentiment_score": round(avg_score, 6),
                "confidence": round(avg_conf, 6),
                "source": latest.provenance.source,
                "created_at": latest.created_at.isoformat(),
            }
        )

    snapshots.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"snapshots": snapshots}


@research_router.get("/sentiment/history/{symbol}")
async def get_sentiment_history(
    symbol: str,
    days: int = Query(30, ge=1, le=365),
):
    cutoff = _utc_now() - timedelta(days=days)
    rows = sentiment_ingest.list_by_asset(symbol, limit=10000)
    history = [
        {
            "date": row.created_at.isoformat(),
            "sentiment_score": round(row.sentiment_score, 6),
            "confidence": round(row.provenance.confidence, 6),
            "source": row.provenance.source,
        }
        for row in rows
        if row.created_at >= cutoff
    ]
    history.sort(key=lambda item: item["date"])
    return {"symbol": symbol.upper(), "history": history}


# ====================================================================
# Blog Endpoints (live-backed)
# ====================================================================


@blog_router.get("/posts", response_model=dict)
async def get_blog_posts(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query("published"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    normalized_status = str(status or "published").strip().lower()
    if normalized_status not in {"published", "pending_review", "needs_revision", "all"}:
        raise HTTPException(status_code=400, detail="invalid_blog_status")
    return blog_service.list_posts(limit=limit, offset=offset, category=category, status=normalized_status)


@blog_router.get("/posts/{post_id}", response_model=dict)
async def get_blog_post(post_id: str):
    post = blog_service.get_post_detail(post_id, increment_views=True)
    if post is None:
        raise HTTPException(status_code=404, detail="blog_post_not_found")
    return post


@blog_router.post("/posts/generate", response_model=dict)
async def generate_blog_post(body: BlogGenerateIn):
    run_id = body.run_id or f"run-blog-agent-{uuid.uuid4().hex[:10]}"
    queue_result = fund_agent_runtime.enqueue_ceo_command(
        run_id=run_id,
        command=body.command,
        agent_id="ceo",
        target_role="blog_writer",
        payload={
            "report_ids": list(body.report_ids or []),
            "symbol": body.symbol,
            "command": body.command,
            "trigger_source": "api.blog.generate",
        },
        priority=max(0, min(10, int(body.priority))),
    )
    return {
        "accepted": True,
        "run_id": run_id,
        "queued": queue_result,
    }


@router.get("/ceo/digest", response_model=dict)
async def get_ceo_digest():
    return vektor_ceo_service.digest()


@router.get("/ceo/position/{symbol}", response_model=dict)
async def get_ceo_position(symbol: str):
    result = vektor_ceo_service.position_brief(symbol)
    if not result.get("accepted"):
        raise HTTPException(status_code=404, detail=result.get("reason") or "position_not_found")
    return result


@router.get("/ceo/performance-breakdown", response_model=dict)
async def get_ceo_performance_breakdown():
    return vektor_ceo_service.portfolio_performance_breakdown()


@router.get("/ceo/positions", response_model=dict)
async def get_ceo_positions():
    return vektor_ceo_service.positions_summary()


@router.get("/ceo/winners-losers", response_model=dict)
async def get_ceo_winners_losers():
    return vektor_ceo_service.winners_losers()


@router.get("/ceo/exposure", response_model=dict)
async def get_ceo_exposure():
    return vektor_ceo_service.exposure_by_asset_class()


@router.get("/ceo/risk-alerts", response_model=dict)
async def get_ceo_risk_alerts():
    return vektor_ceo_service.risk_alerts()


@router.get("/ceo/ml-effectiveness", response_model=dict)
async def get_ceo_ml_effectiveness():
    return vektor_ceo_service.ml_effectiveness_snapshot()


@router.get("/ceo/command-help", response_model=dict)
async def get_ceo_command_help():
    return vektor_ceo_service.command_help()


@router.get("/ceo/digests", response_model=dict)
async def get_ceo_digests(
    limit: int = Query(default=20, ge=1, le=200),
    digest_type: str | None = Query(default=None, min_length=3, max_length=64),
):
    return {"digests": vektor_ceo_service.list_digests(limit=limit, digest_type=digest_type)}


@router.post("/ceo/digest/generate", response_model=dict)
async def generate_ceo_digest():
    return vektor_ceo_service.persist_digest(digest_type="manual", generated_by="api.admin")


@router.get("/ceo/approvals/pending", response_model=dict)
async def get_pending_approvals(
    limit: int = Query(default=50, ge=1, le=500),
    request_type: str | None = Query(default=None, min_length=3, max_length=64),
):
    return {"approvals": firm_orchestrator.list_pending_approvals(limit=limit, request_type=request_type)}


@router.get("/ceo/approvals/{request_id}", response_model=dict)
async def get_approval_detail(request_id: str):
    approval = firm_orchestrator.get_approval_request(request_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval_request_not_found")
    payload = dict(approval.get("payload") or {})
    decision_id = str(payload.get("decision_id") or "").strip()
    if decision_id:
        decision = next((item for item in decision_ledger.list_decisions() if item.decision_id == decision_id), None)
        if decision is not None:
            discovery_snapshot = firm_orchestrator.latest_discovery_opportunity(
                run_id=decision.run_id,
                symbol=(payload.get("intent") or {}).get("symbol") or "",
            )
            approval = {
                **approval,
                "decision": {
                    "decision_id": decision.decision_id,
                    "run_id": decision.run_id,
                    "status": decision.status,
                    "sleeve": decision.sleeve.value,
                },
                "risk_gate": payload.get("risk_gate"),
                "decision_scoring": payload.get("decision_scoring") or (
                    {
                        "score": discovery_snapshot.get("score"),
                        "confidence": discovery_snapshot.get("confidence"),
                        "direction": discovery_snapshot.get("direction"),
                        "asset_class": discovery_snapshot.get("asset_class"),
                        "strategy_family": discovery_snapshot.get("strategy_family"),
                        "horizon": discovery_snapshot.get("horizon"),
                        "math_summary": (discovery_snapshot.get("ml") or {}).get("math_summary"),
                        "metrics": dict((discovery_snapshot.get("ml") or {})),
                    }
                    if discovery_snapshot
                    else None
                ),
            }
    return approval


@router.post("/ceo/approvals/{request_id}/approve", response_model=dict)
async def approve_request(request_id: str, body: RuntimeControlIn):
    try:
        return firm_orchestrator.approve_request(request_id, reviewed_by="api.admin", notes=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ceo/approvals/{request_id}/reject", response_model=dict)
async def reject_request(request_id: str, body: RuntimeControlIn):
    try:
        return firm_orchestrator.reject_request(request_id, reviewed_by="api.admin", notes=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/ceo/editorial/pending", response_model=dict)
async def get_pending_editorial():
    return vektor_ceo_service.pending_editorial_queue()


@router.get("/ceo/editorial/{post_id}", response_model=dict)
async def get_editorial_detail(post_id: str):
    result = vektor_ceo_service.editorial_detail(post_id)
    if not result.get("accepted"):
        raise HTTPException(status_code=404, detail=result.get("reason") or "editorial_not_found")
    return result


@router.post("/ceo/editorial/{post_id}/approve", response_model=dict)
async def approve_editorial(post_id: str, body: RuntimeControlIn):
    result = vektor_ceo_service.approve_editorial(post_id, approved_by="api.admin", notes=body.reason)
    if not result.get("accepted"):
        raise HTTPException(status_code=404, detail=result.get("reason") or "editorial_not_found")
    return result


@router.post("/ceo/editorial/{post_id}/reject", response_model=dict)
async def reject_editorial(post_id: str, body: RuntimeControlIn):
    result = vektor_ceo_service.reject_editorial(post_id, rejected_by="api.admin", notes=body.reason)
    if not result.get("accepted"):
        raise HTTPException(status_code=404, detail=result.get("reason") or "editorial_not_found")
    return result


@router.get("/ceo/market-watch", response_model=dict)
async def get_market_watch():
    return vektor_ceo_service.market_watch()
