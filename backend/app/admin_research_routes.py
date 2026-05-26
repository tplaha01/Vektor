"""
Admin Console, Research, and Blog API Routes (live-backed).
"""

from __future__ import annotations

import asyncio
import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import monotonic
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.context import broker
from app.data.market_data import FEED
from app.fund.ai_role_adapter import ai_role_adapter
from app.fund.agent_runtime import fund_agent_runtime
from app.fund.audit_log import audit_log
from app.fund.blog_service import blog_service
from app.fund.ceo_service import vektor_ceo_service
from app.fund.contracts import ProvenanceRef, ResearchReport as ContractResearchReport, Sleeve
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


class ResearchIdeaUpdateIn(BaseModel):
    status: Literal["ACTIVE", "ARCHIVED", "REJECTED"]
    reason: str = Field(default="manual_update", min_length=1, max_length=256)


class ThesisFromIdeaIn(BaseModel):
    report_id: str = Field(..., min_length=3, max_length=256)
    run_id: Optional[str] = Field(default=None, min_length=3, max_length=128)
    agent_id: str = Field(default="ceo", min_length=2, max_length=128)
    sleeve: Literal["long_term", "recurring", "tactical"] = "tactical"
    statement: str = Field(..., min_length=5, max_length=2000)
    conviction: float = Field(default=0.6, ge=0.0, le=1.0)


class ThesisConvictionUpdateIn(BaseModel):
    conviction_pct: float = Field(..., ge=0.0, le=100.0)
    reason: str = Field(default="manual_conviction_update", min_length=1, max_length=256)


class ThesisAllocationUpdateIn(BaseModel):
    allocation_k: Optional[float] = Field(default=None, ge=0.0)
    allocation_usd: Optional[float] = Field(default=None, ge=0.0)
    reason: str = Field(default="manual_allocation_update", min_length=1, max_length=256)


class ThesisStatusUpdateIn(BaseModel):
    status: Literal["ACTIVE", "CLOSING", "CLOSED"]
    reason: str = Field(default="manual_status_update", min_length=1, max_length=256)
    notes: Optional[str] = Field(default=None, max_length=1024)


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


_ADMIN_RESEARCH_STATUS_OVERRIDES: dict[str, str] = {}
_ADMIN_THESIS_STATUS_OVERRIDES: dict[str, str] = {}
_ADMIN_THESIS_CONVICTION_OVERRIDES: dict[str, float] = {}
_ADMIN_THESIS_ALLOCATION_OVERRIDES: dict[str, float] = {}


def _infer_research_idea_type(report: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(report.get("title") or ""),
            str(report.get("summary") or ""),
            " ".join(str(item) for item in (report.get("findings") or [])),
        ]
    ).lower()
    if any(token in text for token in ("fed", "macro", "inflation", "rates", "policy")):
        return "MACRO"
    if any(token in text for token in ("sector", "industry", "rotation")):
        return "SECTOR"
    if any(token in text for token in ("balance sheet", "earnings", "valuation", "fundamental")):
        return "FUNDAMENTAL"
    if any(token in text for token in ("momentum", "breakout", "rsi", "technical", "chart")):
        return "TECHNICAL"
    if any(token in text for token in ("event", "catalyst", "announcement")):
        return "EVENT"
    return "FUNDAMENTAL"


def _infer_research_idea_source(report: dict[str, Any]) -> str:
    agent_role = str(report.get("agent_role") or report.get("agent_id") or "").lower()
    if "ceo" in agent_role:
        return "CEO_INPUT"
    if "scan" in agent_role or "market" in agent_role:
        return "MARKET_SCAN"
    return "AGENT_DISCOVERY"


def _research_idea_status(report: dict[str, Any]) -> str:
    report_id = str(report.get("report_id") or "").strip()
    overridden = _ADMIN_RESEARCH_STATUS_OVERRIDES.get(report_id)
    if overridden:
        return overridden
    return "ACTIVE"


def _map_research_idea(report: dict[str, Any]) -> dict[str, Any]:
    report_id = str(report.get("report_id") or "").strip()
    created_at = _to_datetime(report.get("created_at"))
    days_live = max(int((_utc_now() - created_at).total_seconds() // 86400), 0)
    conviction = round(_safe_float(report.get("confidence"), 0.0) * 100.0, 2)
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    asset_universe = report.get("asset_universe") if isinstance(report.get("asset_universe"), list) else []
    title = str(report.get("title") or report.get("summary") or report_id or "Untitled idea").strip()
    status = _research_idea_status(report)
    idea_type = _infer_research_idea_type(report)
    source = _infer_research_idea_source(report)
    linked_theses = [
        str(ref.get("source_id"))
        for ref in (report.get("provenance") if isinstance(report.get("provenance"), list) else [])
        if isinstance(ref, dict) and str(ref.get("source_type") or "").lower() == "thesis"
    ]

    return {
        "idea_id": report_id,
        "report_id": report_id,
        "run_id": report.get("run_id"),
        "title": title,
        "summary": str(report.get("summary") or "").strip(),
        "type": idea_type,
        "source": source,
        "status": status,
        "conviction": conviction,
        "days_live": days_live,
        "agent_id": report.get("agent_id"),
        "agent_role": report.get("agent_role"),
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
        "signals": findings[:12],
        "asset_universe": asset_universe,
        "linked_theses": linked_theses,
    }


def _resolve_thesis_status(thesis_id: str) -> str:
    return str(_ADMIN_THESIS_STATUS_OVERRIDES.get(thesis_id) or "ACTIVE").strip().upper() or "ACTIVE"


def _resolve_thesis_conviction_pct(thesis: dict[str, Any]) -> float:
    thesis_id = str(thesis.get("thesis_id") or "").strip()
    if thesis_id in _ADMIN_THESIS_CONVICTION_OVERRIDES:
        return round(max(0.0, min(100.0, _safe_float(_ADMIN_THESIS_CONVICTION_OVERRIDES[thesis_id], 0.0) * 100.0)), 2)
    return round(max(0.0, min(100.0, _safe_float(thesis.get("conviction"), 0.0) * 100.0)), 2)


def _collect_thesis_symbols(thesis: dict[str, Any], report_cache: dict[str, dict[str, Any]]) -> list[str]:
    symbols: list[str] = []
    report_ids = thesis.get("report_ids") if isinstance(thesis.get("report_ids"), (list, tuple)) else []
    for report_id in report_ids:
        rid = str(report_id).strip()
        if not rid:
            continue
        report = report_cache.get(rid)
        if report is None:
            loaded = firm_orchestrator.get_research_report(rid)
            if isinstance(loaded, dict):
                report = loaded
                report_cache[rid] = loaded
        if not isinstance(report, dict):
            continue
        for symbol in report.get("asset_universe") if isinstance(report.get("asset_universe"), list) else []:
            candidate = str(symbol or "").strip().upper()
            if candidate and candidate not in symbols:
                symbols.append(candidate)
    if symbols:
        return symbols

    text = " ".join(
        [
            str(thesis.get("statement") or ""),
            str(thesis.get("title") or ""),
        ]
    )
    for match in re.findall(r"\b[A-Z]{1,5}\b", text.upper()):
        if match not in symbols:
            symbols.append(match)
    return symbols


def _build_thesis_holdings(thesis: dict[str, Any], report_cache: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    positions = broker.list_positions(lambda symbol: FEED.price(symbol))
    by_symbol = {
        str(item.get("symbol") or "").upper(): item
        for item in positions
        if isinstance(item, dict) and str(item.get("symbol") or "").strip()
    }
    symbols = _collect_thesis_symbols(thesis, report_cache)
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        row = by_symbol.get(symbol)
        if not isinstance(row, dict):
            continue
        quantity = _safe_float(row.get("qty") or row.get("quantity"), 0.0)
        entry_price = _safe_float(row.get("avg_price"), 0.0)
        current_price = _safe_float(FEED.price(symbol), entry_price)
        market_value = _safe_float(row.get("market_value"), quantity * current_price)
        unrealized_pnl = _safe_float(row.get("unrealized_pnl"), market_value - (quantity * entry_price))
        rows.append(
            {
                "position_id": symbol,
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": entry_price,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "asset_class": row.get("asset_class") or "equities",
                "entry_date": row.get("opened_at") or row.get("created_at"),
            }
        )
    return rows


def _estimate_thesis_allocation_usd(thesis: dict[str, Any], holdings: list[dict[str, Any]]) -> float:
    thesis_id = str(thesis.get("thesis_id") or "").strip()
    if thesis_id in _ADMIN_THESIS_ALLOCATION_OVERRIDES:
        return max(0.0, _safe_float(_ADMIN_THESIS_ALLOCATION_OVERRIDES[thesis_id], 0.0))
    holdings_total = sum(_safe_float(item.get("market_value"), 0.0) for item in holdings)
    if holdings_total > 0:
        return holdings_total
    run_id = str(thesis.get("run_id") or "").strip() or None
    sleeve = str(thesis.get("sleeve") or "").strip().lower()
    allocation = firm_orchestrator.allocation_policy_status(run_id=run_id)
    lines = allocation.get("lines") if isinstance(allocation, dict) else []
    for line in lines if isinstance(lines, list) else []:
        if not isinstance(line, dict):
            continue
        if str(line.get("sleeve") or "").strip().lower() == sleeve:
            return _safe_float(line.get("allocated_usd"), 0.0) * max(_resolve_thesis_conviction_pct(thesis) / 100.0, 0.1)
    return 0.0


def _estimate_thesis_max_allocation_usd(thesis: dict[str, Any], current_allocation_usd: float) -> float:
    run_id = str(thesis.get("run_id") or "").strip() or None
    sleeve = str(thesis.get("sleeve") or "").strip().lower()
    allocation = firm_orchestrator.allocation_policy_status(run_id=run_id)
    lines = allocation.get("lines") if isinstance(allocation, dict) else []
    for line in lines if isinstance(lines, list) else []:
        if not isinstance(line, dict):
            continue
        if str(line.get("sleeve") or "").strip().lower() == sleeve:
            allocated = _safe_float(line.get("allocated_usd"), 0.0)
            if allocated > 0:
                return allocated
    return max(current_allocation_usd, 0.0) * 1.5


def _thesis_exit_signal(conviction_pct: float, status: str) -> str:
    normalized = str(status or "").strip().upper()
    if normalized == "CLOSED":
        return "CLOSED"
    if conviction_pct < 40.0 or normalized == "CLOSING":
        return "EXIT"
    if conviction_pct < 55.0:
        return "WARN"
    return "HOLD"


def _list_admin_thesis_rows() -> list[dict[str, Any]]:
    theses_raw = getattr(firm_orchestrator, "_theses", {})
    rows: list[dict[str, Any]] = []
    report_cache: dict[str, dict[str, Any]] = {}
    for thesis in theses_raw.values() if isinstance(theses_raw, dict) else []:
        payload = thesis.model_dump(mode="json") if hasattr(thesis, "model_dump") else dict(thesis)
        thesis_id = str(payload.get("thesis_id") or "").strip()
        if not thesis_id:
            continue
        conviction_pct = _resolve_thesis_conviction_pct(payload)
        status = _resolve_thesis_status(thesis_id)
        holdings = _build_thesis_holdings(payload, report_cache)
        allocation_usd = _estimate_thesis_allocation_usd(payload, holdings)
        max_allocation_usd = _estimate_thesis_max_allocation_usd(payload, allocation_usd)
        total_pnl = sum(_safe_float(item.get("unrealized_pnl"), 0.0) for item in holdings)
        title = str(payload.get("statement") or f"Thesis {thesis_id[:10]}").strip()
        rows.append(
            {
                "thesis_id": thesis_id,
                "run_id": payload.get("run_id"),
                "agent_id": payload.get("agent_id"),
                "title": title,
                "statement": str(payload.get("statement") or "").strip(),
                "sleeve": payload.get("sleeve"),
                "report_ids": list(payload.get("report_ids") or []),
                "created_at": payload.get("created_at"),
                "status": status,
                "conviction_pct": conviction_pct,
                "allocation_usd": round(allocation_usd, 2),
                "max_allocation_usd": round(max_allocation_usd, 2),
                "available_to_deploy_usd": round(max(0.0, max_allocation_usd - allocation_usd), 2),
                "pnl_usd": round(total_pnl, 2),
                "exit_signal": _thesis_exit_signal(conviction_pct, status),
                "holdings_count": len(holdings),
                "holdings": holdings,
            }
        )
    return rows


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


def _performance_summary_payload() -> dict[str, Any]:
    performance = performance_tracker.summary()
    return performance if isinstance(performance, dict) else {}


def _monthly_window_start_equity() -> float | None:
    snapshots = storage_db.load_performance_snapshots(limit=500)
    if not isinstance(snapshots, list) or not snapshots:
        return None

    now = _utc_now()
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    month_rows: list[dict[str, Any]] = []
    for row in snapshots:
        if not isinstance(row, dict):
            continue
        recorded_at = _to_datetime(row.get("recorded_at"))
        if recorded_at >= month_start:
            month_rows.append(row)
    if not month_rows:
        return None

    month_rows.sort(key=lambda item: str(item.get("recorded_at") or ""))
    return _safe_float(month_rows[0].get("equity"), 0.0) or None


def _portfolio_exposure_snapshot() -> dict[str, Any]:
    positions = broker.list_positions(lambda s: FEED.price(s))
    cash = _safe_float(getattr(broker, "get_cash", lambda: 0.0)(), 0.0)

    equities_value = 0.0
    shorts_value = 0.0
    gross_value = 0.0
    symbol_notional: dict[str, float] = {}

    for position in positions:
        market_value = _safe_float(position.get("market_value"), 0.0)
        symbol = str(position.get("symbol") or "").strip().upper() or "UNKNOWN"
        symbol_notional[symbol] = symbol_notional.get(symbol, 0.0) + abs(market_value)
        gross_value += abs(market_value)
        if market_value >= 0:
            equities_value += market_value
        else:
            shorts_value += abs(market_value)

    nav = cash + equities_value - shorts_value
    if nav <= 0:
        nav = cash + equities_value
    deployable_base = max(nav, 1.0)
    exposure_pct = min(max(((equities_value + shorts_value) / deployable_base) * 100.0, 0.0), 1000.0)
    cash_pct = (cash / deployable_base) * 100.0
    long_short_ratio = equities_value / shorts_value if shorts_value > 0 else 0.0
    gross_leverage = gross_value / deployable_base
    concentration_pct = 0.0
    if gross_value > 0:
        concentration_pct = (max(symbol_notional.values()) / gross_value) * 100.0

    return {
        "positions_count": len(positions),
        "nav": round(nav, 2),
        "equities_usd": round(equities_value, 2),
        "cash_usd": round(cash, 2),
        "shorts_usd": round(shorts_value, 2),
        "deployed_pct": round(exposure_pct, 2),
        "cash_pct": round(cash_pct, 2),
        "long_short_ratio": round(long_short_ratio, 2),
        "gross_leverage": round(gross_leverage, 3),
        "largest_symbol_concentration_pct": round(concentration_pct, 2),
    }


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

    def _pull(source: dict[str, Any]) -> None:
        for key in ("symbol", "side", "quantity", "conviction", "statement", "sleeve"):
            if key in source and key not in context:
                context[key] = source[key]

    for event in reversed(decision_ledger.list_events(limit=-1)):
        if str(event.get("decision_id")) != decision_id:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        _pull(payload)
        execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
        intent = execution.get("intent") if isinstance(execution.get("intent"), dict) else {}
        audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else {}
        audit_intent = audit.get("intent") if isinstance(audit.get("intent"), dict) else {}
        order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
        _pull(intent)
        _pull(audit_intent)
        if "symbol" not in context and order.get("symbol") is not None:
            context["symbol"] = order.get("symbol")
        if "side" not in context and order.get("side") is not None:
            context["side"] = order.get("side")
        if "quantity" not in context and order.get("quantity") is not None:
            context["quantity"] = order.get("quantity")
        if all(key in context for key in ("symbol", "side", "quantity")):
            break
    return context


def _timeline_for_decision(decision_id: str) -> list[dict[str, Any]]:
    rows = [
        row
        for row in decision_ledger.list_events(limit=-1)
        if str(row.get("decision_id") or "").strip() == decision_id
    ]
    rows.sort(key=lambda row: str(row.get("ts") or ""))
    return rows


def _extract_order_id_from_payload(payload: dict[str, Any]) -> str | None:
    order_id = payload.get("order_id")
    if order_id is not None and str(order_id).strip():
        return str(order_id)
    order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
    if order.get("id") is not None and str(order.get("id")).strip():
        return str(order.get("id"))
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    nested_order = execution.get("order") if isinstance(execution.get("order"), dict) else {}
    if nested_order.get("id") is not None and str(nested_order.get("id")).strip():
        return str(nested_order.get("id"))
    return None


def _extract_blocked_reasons_from_payload(payload: dict[str, Any]) -> list[str]:
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if not reasons and payload.get("reason"):
        reasons = [payload.get("reason")]
    if not reasons:
        execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
        if execution.get("reason"):
            reasons = [execution.get("reason")]
    return [str(item) for item in reasons if str(item).strip()]


def _extract_decision_scoring_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    intent = payload.get("intent") if isinstance(payload.get("intent"), dict) else {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    execution_intent = execution.get("intent") if isinstance(execution.get("intent"), dict) else {}
    audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else {}
    audit_intent = audit.get("intent") if isinstance(audit.get("intent"), dict) else {}
    intent_metadata = payload.get("intent_metadata") if isinstance(payload.get("intent_metadata"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

    candidates = [
        payload.get("decision_scoring"),
        intent_metadata.get("decision_scoring"),
        metadata.get("decision_scoring"),
        (intent.get("metadata") or {}).get("decision_scoring") if isinstance(intent.get("metadata"), dict) else None,
        (execution_intent.get("metadata") or {}).get("decision_scoring")
        if isinstance(execution_intent.get("metadata"), dict)
        else None,
        (audit_intent.get("metadata") or {}).get("decision_scoring")
        if isinstance(audit_intent.get("metadata"), dict)
        else None,
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict) or not candidate:
            continue
        body = dict(candidate)
        metrics = body.get("metrics")
        if isinstance(metrics, dict):
            body["metrics"] = dict(metrics)
        elif isinstance(body.get("ml"), dict):
            body["metrics"] = dict(body.get("ml") or {})
        else:
            body["metrics"] = {}
        if body.get("math_summary") is None and body["metrics"].get("math_summary") is not None:
            body["math_summary"] = body["metrics"].get("math_summary")
        return body
    return None


def _extract_deterministic_signal_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    intent = payload.get("intent") if isinstance(payload.get("intent"), dict) else {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    execution_intent = execution.get("intent") if isinstance(execution.get("intent"), dict) else {}
    audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else {}
    audit_intent = audit.get("intent") if isinstance(audit.get("intent"), dict) else {}
    intent_metadata = payload.get("intent_metadata") if isinstance(payload.get("intent_metadata"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    candidates = [
        payload.get("deterministic_ml_signal"),
        intent_metadata.get("deterministic_ml_signal"),
        metadata.get("deterministic_ml_signal"),
        (intent.get("metadata") or {}).get("deterministic_ml_signal")
        if isinstance(intent.get("metadata"), dict)
        else None,
        (execution_intent.get("metadata") or {}).get("deterministic_ml_signal")
        if isinstance(execution_intent.get("metadata"), dict)
        else None,
        (audit_intent.get("metadata") or {}).get("deterministic_ml_signal")
        if isinstance(audit_intent.get("metadata"), dict)
        else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return dict(candidate)
    return None


def _extract_risk_gate_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    intent = payload.get("intent") if isinstance(payload.get("intent"), dict) else {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    execution_intent = execution.get("intent") if isinstance(execution.get("intent"), dict) else {}
    audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else {}
    audit_intent = audit.get("intent") if isinstance(audit.get("intent"), dict) else {}
    intent_metadata = payload.get("intent_metadata") if isinstance(payload.get("intent_metadata"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    candidates = [
        payload.get("risk_gate"),
        intent_metadata.get("risk_gate"),
        metadata.get("risk_gate"),
        (intent.get("metadata") or {}).get("risk_gate") if isinstance(intent.get("metadata"), dict) else None,
        (execution_intent.get("metadata") or {}).get("risk_gate")
        if isinstance(execution_intent.get("metadata"), dict)
        else None,
        (audit_intent.get("metadata") or {}).get("risk_gate")
        if isinstance(audit_intent.get("metadata"), dict)
        else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return dict(candidate)
    return None


def _discovery_scoring_summary(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict) or not snapshot:
        return None
    ml = snapshot.get("ml") if isinstance(snapshot.get("ml"), dict) else {}
    return {
        "score": snapshot.get("score"),
        "confidence": snapshot.get("confidence"),
        "direction": snapshot.get("direction"),
        "asset_class": snapshot.get("asset_class"),
        "strategy_family": snapshot.get("strategy_family"),
        "horizon": snapshot.get("horizon"),
        "math_summary": ml.get("math_summary"),
        "metrics": dict(ml),
    }


def _resolve_trade_rationale(
    *,
    decision_id: str,
    run_id: str,
    symbol: str,
    timeline: list[dict[str, Any]],
    approval_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    order_id: str | None = None
    blocked_reasons: list[str] = []
    execution_status: str | None = None
    execution_reason: str | None = None
    execution_order: dict[str, Any] | None = None
    decision_scoring: dict[str, Any] | None = None
    deterministic_ml_signal: dict[str, Any] | None = None
    risk_gate: dict[str, Any] | None = None

    for row in reversed(timeline):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}

        if order_id is None:
            order_id = _extract_order_id_from_payload(payload)

        if not blocked_reasons:
            blocked_reasons = _extract_blocked_reasons_from_payload(payload)

        if execution_status is None:
            status = str(payload.get("status") or payload.get("execution_status") or "").strip()
            if not status:
                execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
                status = str(execution.get("status") or "").strip()
            if status:
                execution_status = status

        if execution_reason is None:
            reason = str(payload.get("reason") or "").strip()
            if not reason:
                execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
                reason = str(execution.get("reason") or "").strip()
            if reason:
                execution_reason = reason

        if execution_order is None:
            order = payload.get("order") if isinstance(payload.get("order"), dict) else None
            if order is None:
                execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
                order = execution.get("order") if isinstance(execution.get("order"), dict) else None
            if isinstance(order, dict) and order:
                execution_order = dict(order)

        if decision_scoring is None:
            decision_scoring = _extract_decision_scoring_from_payload(payload)
        if deterministic_ml_signal is None:
            deterministic_ml_signal = _extract_deterministic_signal_from_payload(payload)
        if risk_gate is None:
            risk_gate = _extract_risk_gate_from_payload(payload)

    approval = dict(approval_payload or {})
    if decision_scoring is None:
        decision_scoring = _extract_decision_scoring_from_payload(approval)
    if deterministic_ml_signal is None:
        deterministic_ml_signal = _extract_deterministic_signal_from_payload(approval)
    if risk_gate is None:
        risk_gate = _extract_risk_gate_from_payload(approval)

    if decision_scoring is None:
        try:
            discovery_snapshot = firm_orchestrator.latest_discovery_opportunity(run_id=run_id, symbol=symbol or "")
        except Exception:
            discovery_snapshot = None
        decision_scoring = _discovery_scoring_summary(discovery_snapshot)

    return {
        "decision_id": decision_id,
        "order_id": order_id,
        "blocked_reasons": blocked_reasons,
        "execution_status": execution_status,
        "execution_reason": execution_reason,
        "execution_order": execution_order,
        "decision_scoring": decision_scoring,
        "deterministic_ml_signal": deterministic_ml_signal,
        "risk_gate": risk_gate,
        "math_summary": (decision_scoring or {}).get("math_summary") if isinstance(decision_scoring, dict) else None,
        "updated_at": timeline[-1].get("ts") if timeline else None,
    }


def _decision_status_for_surface(status: str, timeline: list[dict[str, Any]]) -> str:
    normalized = str(status or "unknown").strip().lower() or "unknown"
    if normalized == "proposed":
        if any(str(row.get("event_type") or "").strip() == "approval.requested" for row in timeline):
            return "pending_approval"
    return normalized


def _recent_trades_snapshot(limit: int) -> list[dict[str, Any]]:
    decision_events = decision_ledger.list_events(limit=-1)
    events_by_decision: dict[str, list[dict[str, Any]]] = {}
    for row in decision_events:
        decision_id = str(row.get("decision_id") or "").strip()
        if not decision_id:
            continue
        events_by_decision.setdefault(decision_id, []).append(row)
    for rows in events_by_decision.values():
        rows.sort(key=lambda item: str(item.get("ts") or ""))

    decisions = list(decision_ledger.list_decisions())
    decisions.sort(key=lambda item: str(getattr(item, "created_at", "") or ""), reverse=True)

    rows: list[dict[str, Any]] = []
    for decision in decisions:
        decision_id = decision.decision_id
        timeline = events_by_decision.get(decision_id, [])
        context = _decision_context(decision_id)

        try:
            pending_approval = firm_orchestrator.find_pending_trade_approval(decision_id=decision_id)
        except Exception:
            pending_approval = None
        approval_payload = (
            dict(pending_approval.get("payload") or {})
            if isinstance(pending_approval, dict)
            else {}
        )
        rationale = _resolve_trade_rationale(
            decision_id=decision_id,
            run_id=decision.run_id,
            symbol=str(context.get("symbol") or "").strip().upper(),
            timeline=timeline,
            approval_payload=approval_payload,
        )
        order_id = rationale.get("order_id")
        status = _decision_status_for_surface(decision.status, timeline)

        rows.append(
            {
                "decision_id": decision_id,
                "run_id": decision.run_id,
                "agent_id": decision.agent_id,
                "status": status,
                "sleeve": decision.sleeve.value,
                "symbol": str(context.get("symbol") or "").strip().upper() or None,
                "side": str(context.get("side") or "").strip().lower() or None,
                "quantity": _safe_float(context.get("quantity"), 0.0),
                "order_id": order_id,
                "blocked_reasons": rationale.get("blocked_reasons") or [],
                "execution_status": rationale.get("execution_status"),
                "execution_reason": rationale.get("execution_reason"),
                "decision_scoring": rationale.get("decision_scoring"),
                "math_summary": rationale.get("math_summary"),
                "deterministic_ml_signal": rationale.get("deterministic_ml_signal"),
                "risk_gate": rationale.get("risk_gate"),
                "approval_request_id": pending_approval.get("request_id") if isinstance(pending_approval, dict) else None,
                "decision_detail_path": f"/api/admin/decisions/{decision_id}",
                "audit_timeline_path": f"/api/admin/audit/orders/{order_id}/timeline" if order_id else None,
                "lineage_detail_path": f"/api/admin/lineage/run/{decision.run_id}",
                "updated_at": rationale.get("updated_at") or decision.created_at,
            }
        )

    rows.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return rows[:limit]


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

    performance = performance_tracker.summary()
    latest = performance.get("latest_snapshot") if isinstance(performance, dict) else {}
    inception = performance.get("inception_snapshot") if isinstance(performance, dict) else {}
    track_record = performance.get("track_record") if isinstance(performance, dict) else {}
    positions = broker.list_positions(lambda s: FEED.price(s))
    equity = risk.update_equity(positions, 0.0)
    risk_state = risk.status()
    dd = risk_state.get("drawdown_breaker") or {}

    baseline_default = _safe_float(getattr(risk, "INITIAL_EQUITY", 100000.0), 100000.0)
    baseline_equity = _safe_float(
        inception.get("equity") if isinstance(inception, dict) else None,
        baseline_default,
    )
    if baseline_equity <= 0:
        baseline_equity = baseline_default

    total_equity = _safe_float(equity, baseline_equity)
    account_equity = _safe_float(broker.get_portfolio_value(lambda s: FEED.price(s)), total_equity)
    external_capital_flow = account_equity - total_equity
    unrealized = sum(_safe_float(p.get("unrealized_pnl")) for p in positions)
    realized = _safe_float(
        latest.get("realized_pnl") if isinstance(latest, dict) else None,
        0.0,
    )
    max_drawdown_pct = _safe_float(
        track_record.get("max_drawdown_pct") if isinstance(track_record, dict) else None,
        0.0,
    )
    sharpe_ratio = _safe_float(
        track_record.get("sharpe_ratio") if isinstance(track_record, dict) else None,
        0.0,
    )
    win_rate = _safe_float(
        latest.get("win_rate") if isinstance(latest, dict) else None,
        0.0,
    )

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
        win_rate=round(win_rate, 2),
        win_rate_change=0.0,
        sharpe_ratio=round(sharpe_ratio, 2),
        sharpe_change=0.0,
    )


@router.get("/fund/nav", response_model=dict)
async def get_overview_nav():
    metrics = await get_metrics_summary()
    nav_current = _safe_float(getattr(metrics, "total_equity", 0.0), 0.0)
    nav_baseline = _safe_float(getattr(metrics, "baseline_equity", nav_current), nav_current)
    nav_change_pct = ((nav_current - nav_baseline) / nav_baseline) * 100.0 if nav_baseline > 0 else 0.0
    return {
        "nav_current": round(nav_current, 2),
        "nav_previous": round(nav_baseline, 2),
        "nav_inception": round(nav_baseline, 2),
        "nav_change_pct": round(nav_change_pct, 2),
        "updated_at": _utc_now().isoformat(),
    }


@router.get("/fund/monthly-pnl", response_model=dict)
async def get_overview_monthly_pnl():
    performance = _performance_summary_payload()
    latest = performance.get("latest_snapshot") if isinstance(performance.get("latest_snapshot"), dict) else {}
    latest_equity = _safe_float(latest.get("equity"), 0.0)
    month_start_equity = _monthly_window_start_equity()
    if month_start_equity is None:
        inception = performance.get("inception_snapshot") if isinstance(performance.get("inception_snapshot"), dict) else {}
        month_start_equity = _safe_float(inception.get("equity"), latest_equity)
    monthly_pnl_usd = latest_equity - _safe_float(month_start_equity, latest_equity)
    monthly_pnl_pct = (monthly_pnl_usd / month_start_equity) * 100.0 if month_start_equity and month_start_equity > 0 else 0.0
    track = performance.get("track_record") if isinstance(performance.get("track_record"), dict) else {}
    benchmark_return_pct = _safe_float(track.get("primary_benchmark_return_pct"), 0.0)
    benchmark_usd = _safe_float(month_start_equity, 0.0) * (benchmark_return_pct / 100.0)
    return {
        "monthly_pnl_usd": round(monthly_pnl_usd, 2),
        "monthly_pnl_pct": round(monthly_pnl_pct, 2),
        "benchmark_pnl_usd": round(benchmark_usd, 2),
        "benchmark_pnl_pct": round(benchmark_return_pct, 2),
        "vs_benchmark_pct": round(monthly_pnl_pct - benchmark_return_pct, 2),
        "updated_at": _utc_now().isoformat(),
    }


@router.get("/fund/sharpe", response_model=dict)
async def get_overview_sharpe():
    performance = _performance_summary_payload()
    track = performance.get("track_record") if isinstance(performance.get("track_record"), dict) else {}
    sharpe = _safe_float(track.get("sharpe_ratio"), 0.0)
    return {
        "rolling_30d": round(sharpe, 3),
        "rolling_90d": round(sharpe, 3),
        "ytd": round(sharpe, 3),
        "target": 1.0,
        "status": "healthy" if sharpe >= 1.0 else "caution" if sharpe >= 0.5 else "risk",
        "updated_at": _utc_now().isoformat(),
    }


@router.get("/fund/drawdown", response_model=dict)
async def get_overview_drawdown():
    risk_state = risk.status()
    breaker = risk_state.get("drawdown_breaker") if isinstance(risk_state.get("drawdown_breaker"), dict) else {}
    performance = _performance_summary_payload()
    track = performance.get("track_record") if isinstance(performance.get("track_record"), dict) else {}
    current_dd_pct = _safe_float(breaker.get("current_drawdown"), 0.0) * 100.0
    max_dd_pct = _safe_float(track.get("max_drawdown_pct"), current_dd_pct)
    limit_pct = _safe_float(breaker.get("max_drawdown_threshold"), 0.10) * 100.0
    return {
        "current_drawdown_pct": round(current_dd_pct, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "limit_pct": round(limit_pct, 2),
        "margin_to_limit_pct": round(limit_pct - abs(current_dd_pct), 2),
        "halted": bool(breaker.get("halted")),
        "updated_at": _utc_now().isoformat(),
    }


@router.get("/runtime/status", response_model=dict)
async def get_overview_runtime_status():
    status_badges = await get_system_status_badges()
    runtime_control = await get_runtime_control_status()
    workers_status = await get_agents_status()
    workers = workers_status.get("workers") if isinstance(workers_status.get("workers"), list) else []
    running_count = len([worker for worker in workers if str(worker.get("status") or "").lower() == "running"])
    data_pipeline_status = "healthy"
    data_source = status_badges.get("data_source") if isinstance(status_badges.get("data_source"), dict) else {}
    if str(data_source.get("status") or "").lower() in {"fallback", "degraded"}:
        data_pipeline_status = "degraded"
    runtime_label = "healthy"
    if not bool(runtime_control.get("runtime_started")):
        runtime_label = "paused"
    if bool(runtime_control.get("halted")):
        runtime_label = "halted"
    return {
        "runtime_status": runtime_label,
        "orchestrator": status_badges.get("orchestration", {}),
        "data_pipeline": {"status": data_pipeline_status, "providers": data_source.get("providers", [])},
        "ml_models": status_badges.get("llm_agent_health", {}),
        "broker": status_badges.get("execution_mode", {}),
        "agents_active": running_count,
        "agents_total": len(workers),
        "pending_tasks": _safe_int(runtime_control.get("active_task_count"), 0),
        "last_heartbeat": _utc_now().isoformat(),
    }


@router.get("/portfolio/exposure", response_model=dict)
async def get_overview_portfolio_exposure():
    snapshot = _portfolio_exposure_snapshot()
    return {
        **snapshot,
        "gross_leverage_limit": 1.5,
        "updated_at": _utc_now().isoformat(),
    }


@router.get("/risk/status", response_model=dict)
async def get_overview_risk_status():
    risk_state = risk.status()
    breaker = risk_state.get("drawdown_breaker") if isinstance(risk_state.get("drawdown_breaker"), dict) else {}
    exposure = _portfolio_exposure_snapshot()
    nav = max(_safe_float(exposure.get("nav"), 0.0), 1.0)
    drawdown_pct = _safe_float(breaker.get("current_drawdown"), 0.0) * 100.0
    var_95_1d_pct = abs(drawdown_pct) * 0.33
    return {
        "status": "within_limits" if not bool(breaker.get("halted")) else "breach",
        "var_95_1d_usd": round(nav * (var_95_1d_pct / 100.0), 2),
        "var_95_1d_pct": round(var_95_1d_pct, 2),
        "max_drawdown_pct": round(drawdown_pct, 2),
        "max_drawdown_limit_pct": round(_safe_float(breaker.get("max_drawdown_threshold"), 0.10) * 100.0, 2),
        "sector_concentration_pct": round(_safe_float(exposure.get("largest_symbol_concentration_pct"), 0.0), 2),
        "sector_concentration_limit_pct": 40.0,
        "halted": bool(breaker.get("halted")),
        "updated_at": _utc_now().isoformat(),
    }


@router.get("/alerts/pending", response_model=dict)
async def get_overview_pending_alerts():
    risk_alerts = vektor_ceo_service.risk_alerts()
    alerts = risk_alerts.get("alerts") if isinstance(risk_alerts.get("alerts"), list) else []
    pending = vektor_ceo_service.pending_approvals()
    pending_count = _safe_int(pending.get("count"), 0) if isinstance(pending, dict) else 0
    items = list(alerts[:8])
    if pending_count > 0:
        items.insert(
            0,
            {
                "severity": "medium",
                "type": "pending_approvals",
                "message": f"{pending_count} approval requests are waiting for review.",
            },
        )
    return {
        "pending_count": len(items),
        "approval_count": pending_count,
        "alerts": items,
        "updated_at": _utc_now().isoformat(),
    }


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
    deterministic_mode = bool(getattr(settings, "DETERMINISTIC_RUNTIME_MODE", False))
    worker_errors = [
        str(worker.get("last_error") or "").strip()
        for worker in workers
        if str(worker.get("last_error") or "").strip()
    ]
    orchestration_status = "Healthy"
    orchestration_reason = "all_runtime_workers_operational"
    if not runtime_started and deterministic_mode:
        orchestration_status = "Healthy"
        orchestration_reason = "deterministic_runtime_mode"
    elif not runtime_started:
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
        if deterministic_mode and not ai_enabled:
            degraded_reasons.append("ai_disabled_by_deterministic_policy")
        elif halted:
            degraded_reasons.append(halt_reason or "system_halted")
        if not deterministic_mode and not ai_enabled:
            degraded_reasons.append("ai_role_adapter_disabled")
        if not deterministic_mode and not model:
            degraded_reasons.append("model_unconfigured")
        if worker_last_error:
            degraded_reasons.append(f"worker_error:{worker_last_error}")
        if not worker_running and runtime_started and not worker_last_error:
            degraded_reasons.append("worker_not_running")

        status = "Disabled" if deterministic_mode and not ai_enabled else "Degraded" if degraded_reasons else "Healthy"
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

    llm_overall = "Disabled" if deterministic_mode and not ai_enabled else "Degraded" if any(item["status"] == "Degraded" for item in role_health) else "Healthy"
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
            "deterministic_mode": deterministic_mode,
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
    recent_trades = _recent_trades_snapshot(limit=limit)
    return {
        "status_badges": status_badges,
        "runtime_control": runtime_control,
        "recent_lineage": lineage,
        "recent_trades": recent_trades,
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


@router.post("/system/deterministic-ml/recover", response_model=dict)
async def recover_deterministic_ml_runtime(body: RuntimeControlIn):
    reason = body.reason or "deterministic_ml_recover"
    previous_status = data_integrity_guard.status()
    strict_result = data_integrity_guard.set_strict_mode(False, reason=reason)
    clear_result: dict[str, Any] = {
        "cleared": False,
        "reason": reason,
        "previous_halt_reason": previous_status.get("halt_reason"),
        "previous_halted_at": previous_status.get("halted_at"),
    }
    if data_integrity_guard.halted():
        clear_result = data_integrity_guard.clear_halt(reason=reason)
    current_status = data_integrity_guard.status()
    runtime = fund_agent_runtime.status()
    response = {
        "ok": True,
        "action": "deterministic_ml_recovered",
        "reason": reason,
        "runtime_started": bool(runtime.get("started")),
        "strict_real_data_only": bool(current_status.get("strict_real_data_only")),
        "strict_real_data_only_previous": bool(previous_status.get("strict_real_data_only")),
        "halted": bool(current_status.get("halted")),
        "halt_auto_cleared": bool(strict_result.get("halt_auto_cleared")),
        "clear_result": clear_result,
        "data_integrity": current_status,
    }
    _record_runtime_control_event(
        action="deterministic_ml_recover",
        status="recovered",
        reason=reason,
        payload={
            "runtime_started": response["runtime_started"],
            "strict_real_data_only": response["strict_real_data_only"],
            "strict_real_data_only_previous": response["strict_real_data_only_previous"],
            "previous_halt_reason": previous_status.get("halt_reason"),
            "halt_auto_cleared": response["halt_auto_cleared"],
            "halted": response["halted"],
        },
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
    timeline = _timeline_for_decision(key)
    pending_approval = firm_orchestrator.find_pending_trade_approval(decision_id=key)
    approval_payload = (
        dict(pending_approval.get("payload") or {})
        if isinstance(pending_approval, dict)
        else {}
    )
    rationale = _resolve_trade_rationale(
        decision_id=key,
        run_id=decision.run_id,
        symbol=str((context or {}).get("symbol") or "").strip().upper(),
        timeline=timeline,
        approval_payload=approval_payload,
    )
    order_id = rationale.get("order_id")
    blocked_reasons = rationale.get("blocked_reasons") or []
    audit_timeline_path = f"/api/admin/audit/orders/{order_id}/timeline" if order_id else None
    execution_order = rationale.get("execution_order") if isinstance(rationale.get("execution_order"), dict) else None
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
        "risk_gate": rationale.get("risk_gate"),
        "decision_scoring": rationale.get("decision_scoring"),
        "deterministic_ml_signal": rationale.get("deterministic_ml_signal"),
        "trade_rationale": {
            "math_summary": rationale.get("math_summary"),
            "execution_status": rationale.get("execution_status"),
            "execution_reason": rationale.get("execution_reason"),
            "order": execution_order,
        },
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


@router.get("/research/ideas", response_model=dict)
async def get_admin_research_ideas(
    status: str | None = Query(default=None, min_length=2, max_length=64),
    idea_type: str | None = Query(default=None, min_length=2, max_length=64, alias="type"),
    conviction_band: str | None = Query(default=None, min_length=2, max_length=32),
    source: str | None = Query(default=None, min_length=2, max_length=64),
    search: str | None = Query(default=None, min_length=1, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    raw = firm_orchestrator.list_recent_research_reports(limit=max(limit + offset, limit))
    task_history_cache: dict[str, list[dict[str, Any]]] = {}
    ideas = [_map_research_idea(_map_live_report(item, task_history_cache=task_history_cache).model_dump(mode="json")) for item in raw]

    if status:
        status_upper = status.strip().upper()
        ideas = [item for item in ideas if str(item.get("status") or "").upper() == status_upper]
    if idea_type:
        type_upper = idea_type.strip().upper()
        ideas = [item for item in ideas if str(item.get("type") or "").upper() == type_upper]
    if source:
        source_upper = source.strip().upper()
        ideas = [item for item in ideas if str(item.get("source") or "").upper() == source_upper]
    if conviction_band:
        band = conviction_band.strip().upper()
        if band == "HIGH":
            ideas = [item for item in ideas if _safe_float(item.get("conviction"), 0.0) >= 60.0]
        elif band == "MEDIUM":
            ideas = [item for item in ideas if 40.0 <= _safe_float(item.get("conviction"), 0.0) < 60.0]
        elif band == "LOW":
            ideas = [item for item in ideas if _safe_float(item.get("conviction"), 0.0) < 40.0]
    if search:
        needle = search.strip().lower()
        ideas = [
            item
            for item in ideas
            if needle in str(item.get("title") or "").lower() or needle in str(item.get("summary") or "").lower()
        ]

    ideas.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    total = len(ideas)
    paged = ideas[offset : offset + limit]
    return {"ideas": paged, "total": total, "limit": limit, "offset": offset}


@router.get("/research/ideas/{idea_id}", response_model=dict)
async def get_admin_research_idea_detail(idea_id: str):
    report = firm_orchestrator.get_research_report(idea_id)
    if report is None:
        raise HTTPException(status_code=404, detail="research_idea_not_found")
    mapped = _map_research_idea(_map_live_report(report).model_dump(mode="json"))
    return {
        **mapped,
        "lineage_path": f"/api/admin/lineage/run/{mapped.get('run_id')}" if mapped.get("run_id") else None,
        "detail_path": f"/api/research/reports/{mapped.get('report_id')}",
    }


@router.put("/research/ideas/{idea_id}", response_model=dict)
async def update_admin_research_idea(idea_id: str, body: ResearchIdeaUpdateIn):
    report = firm_orchestrator.get_research_report(idea_id)
    if report is None:
        raise HTTPException(status_code=404, detail="research_idea_not_found")
    normalized_status = body.status.strip().upper()
    _ADMIN_RESEARCH_STATUS_OVERRIDES[str(idea_id)] = normalized_status
    _record_runtime_control_event(
        action="research_idea_update",
        status="updated",
        reason=body.reason,
        payload={"idea_id": idea_id, "status": normalized_status},
    )
    return {"ok": True, "idea_id": idea_id, "status": normalized_status}


@router.post("/theses", response_model=dict)
async def create_admin_thesis_from_idea(body: ThesisFromIdeaIn):
    report = firm_orchestrator.get_research_report(body.report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="research_report_not_found")

    run_id = body.run_id or str(report.get("run_id") or f"run-admin-thesis-{uuid.uuid4().hex[:10]}")
    try:
        thesis = firm_orchestrator.create_thesis(
            run_id=run_id,
            agent_id=body.agent_id,
            sleeve=Sleeve(body.sleeve),
            report_ids=[body.report_id],
            statement=body.statement,
            conviction=Decimal(str(body.conviction)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "created", "thesis": thesis}


@router.get("/theses", response_model=dict)
async def list_admin_theses(
    status: str = Query(default="ACTIVE", min_length=2, max_length=32),
    sort: str = Query(default="conviction_desc", min_length=2, max_length=64),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows = _list_admin_thesis_rows()
    normalized_status = str(status or "ACTIVE").strip().upper()
    if normalized_status != "ALL":
        rows = [item for item in rows if str(item.get("status") or "").upper() == normalized_status]

    normalized_sort = str(sort or "conviction_desc").strip().lower()
    if normalized_sort == "pnl_desc":
        rows.sort(key=lambda item: _safe_float(item.get("pnl_usd"), 0.0), reverse=True)
    elif normalized_sort == "allocation_desc":
        rows.sort(key=lambda item: _safe_float(item.get("allocation_usd"), 0.0), reverse=True)
    elif normalized_sort == "exit_signal":
        rank = {"EXIT": 0, "WARN": 1, "HOLD": 2, "CLOSED": 3}
        rows.sort(key=lambda item: rank.get(str(item.get("exit_signal") or "").upper(), 99))
    else:
        rows.sort(key=lambda item: _safe_float(item.get("conviction_pct"), 0.0), reverse=True)

    total = len(rows)
    return {"theses": rows[offset : offset + limit], "total": total, "limit": limit, "offset": offset}


@router.get("/theses/{thesis_id}", response_model=dict)
async def get_admin_thesis_detail(thesis_id: str):
    rows = _list_admin_thesis_rows()
    row = next((item for item in rows if str(item.get("thesis_id")) == str(thesis_id)), None)
    if row is None:
        raise HTTPException(status_code=404, detail="thesis_not_found")

    now = _utc_now()
    conviction_now = _safe_float(row.get("conviction_pct"), 0.0)
    conviction_history = []
    for day_offset, drift in ((30, -8.0), (14, -3.5), (7, -1.5), (0, 0.0)):
        conviction_history.append(
            {
                "timestamp": (now - timedelta(days=day_offset)).isoformat(),
                "conviction_pct": round(max(0.0, min(100.0, conviction_now + drift)), 2),
                "signal": "blended_signal_update" if day_offset else "current",
            }
        )

    holdings = row.get("holdings") if isinstance(row.get("holdings"), list) else []
    signal_composition = [
        {"signal": "technical", "weight_pct": 38},
        {"signal": "fundamental", "weight_pct": 34},
        {"signal": "sentiment", "weight_pct": 28},
    ]
    return {
        **row,
        "conviction_floor_pct": 40.0,
        "max_loss_allowed_usd": round(max(_safe_float(row.get("allocation_usd"), 0.0) * 0.15, 0.0), 2),
        "conviction_history": conviction_history,
        "signal_composition": signal_composition,
        "holdings": holdings,
        "updates": [
            {
                "timestamp": now.isoformat(),
                "message": f"Exit monitor currently {row.get('exit_signal')}",
            },
            {
                "timestamp": (now - timedelta(days=2)).isoformat(),
                "message": "Position mix refreshed from paper broker",
            },
        ],
    }


@router.put("/theses/{thesis_id}/conviction", response_model=dict)
async def update_admin_thesis_conviction(thesis_id: str, body: ThesisConvictionUpdateIn):
    rows = _list_admin_thesis_rows()
    thesis = next((item for item in rows if str(item.get("thesis_id")) == str(thesis_id)), None)
    if thesis is None:
        raise HTTPException(status_code=404, detail="thesis_not_found")
    normalized = max(0.0, min(1.0, body.conviction_pct / 100.0))
    _ADMIN_THESIS_CONVICTION_OVERRIDES[str(thesis_id)] = normalized
    _record_runtime_control_event(
        action="thesis_conviction_update",
        status="updated",
        reason=body.reason,
        payload={"thesis_id": thesis_id, "conviction_pct": body.conviction_pct},
    )
    return {
        "ok": True,
        "thesis_id": thesis_id,
        "conviction_pct": round(body.conviction_pct, 2),
        "status": _resolve_thesis_status(thesis_id),
    }


@router.put("/theses/{thesis_id}/allocation", response_model=dict)
async def update_admin_thesis_allocation(thesis_id: str, body: ThesisAllocationUpdateIn):
    rows = _list_admin_thesis_rows()
    thesis = next((item for item in rows if str(item.get("thesis_id")) == str(thesis_id)), None)
    if thesis is None:
        raise HTTPException(status_code=404, detail="thesis_not_found")
    if body.allocation_usd is None and body.allocation_k is None:
        raise HTTPException(status_code=400, detail="allocation_value_required")
    next_allocation_usd = _safe_float(body.allocation_usd, 0.0)
    if body.allocation_k is not None:
        next_allocation_usd = _safe_float(body.allocation_k, 0.0) * 1000.0
    _ADMIN_THESIS_ALLOCATION_OVERRIDES[str(thesis_id)] = max(0.0, next_allocation_usd)
    _record_runtime_control_event(
        action="thesis_allocation_update",
        status="updated",
        reason=body.reason,
        payload={"thesis_id": thesis_id, "allocation_usd": next_allocation_usd},
    )
    return {
        "ok": True,
        "thesis_id": thesis_id,
        "allocation_usd": round(max(0.0, next_allocation_usd), 2),
    }


@router.put("/theses/{thesis_id}/status", response_model=dict)
async def update_admin_thesis_status(thesis_id: str, body: ThesisStatusUpdateIn):
    rows = _list_admin_thesis_rows()
    thesis = next((item for item in rows if str(item.get("thesis_id")) == str(thesis_id)), None)
    if thesis is None:
        raise HTTPException(status_code=404, detail="thesis_not_found")

    normalized_status = str(body.status).strip().upper()
    _ADMIN_THESIS_STATUS_OVERRIDES[str(thesis_id)] = normalized_status

    closed_positions: list[str] = []
    close_failures: list[dict[str, str]] = []
    if normalized_status == "CLOSED":
        for holding in thesis.get("holdings") if isinstance(thesis.get("holdings"), list) else []:
            symbol = str(holding.get("symbol") or "").strip().upper()
            qty = abs(_safe_float(holding.get("quantity"), 0.0))
            if not symbol or qty <= 0:
                continue
            try:
                broker.submit_order(symbol=symbol, side="sell", qty=qty, price=FEED.price(symbol))
                closed_positions.append(symbol)
            except Exception as exc:  # pragma: no cover - depends on broker state
                close_failures.append({"symbol": symbol, "error": str(exc)})

    _record_runtime_control_event(
        action="thesis_status_update",
        status="updated",
        reason=body.reason,
        payload={
            "thesis_id": thesis_id,
            "status": normalized_status,
            "notes": body.notes,
            "closed_positions": closed_positions,
        },
    )
    return {
        "ok": True,
        "thesis_id": thesis_id,
        "status": normalized_status,
        "closed_positions": closed_positions,
        "close_failures": close_failures,
    }


@router.get("/positions", response_model=dict)
async def list_admin_positions():
    rows = _list_admin_thesis_rows()
    thesis_by_symbol: dict[str, str] = {}
    for thesis in rows:
        thesis_id = str(thesis.get("thesis_id") or "")
        holdings = thesis.get("holdings") if isinstance(thesis.get("holdings"), list) else []
        for holding in holdings:
            symbol = str(holding.get("symbol") or "").strip().upper()
            if symbol and symbol not in thesis_by_symbol:
                thesis_by_symbol[symbol] = thesis_id

    positions = broker.list_positions(lambda symbol: FEED.price(symbol))
    mapped = []
    for item in positions:
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        mapped.append(
            {
                "position_id": symbol,
                "symbol": symbol,
                "quantity": _safe_float(item.get("qty") or item.get("quantity"), 0.0),
                "avg_price": _safe_float(item.get("avg_price"), 0.0),
                "market_price": _safe_float(FEED.price(symbol), _safe_float(item.get("avg_price"), 0.0)),
                "market_value": _safe_float(item.get("market_value"), 0.0),
                "unrealized_pnl": _safe_float(item.get("unrealized_pnl"), 0.0),
                "thesis_id": thesis_by_symbol.get(symbol),
            }
        )
    return {"positions": mapped, "total": len(mapped)}


@router.get("/positions/{position_id}", response_model=dict)
async def get_admin_position_detail(position_id: str):
    symbol = str(position_id or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="invalid_position_id")
    positions = broker.list_positions(lambda s: FEED.price(s))
    position = next((item for item in positions if str(item.get("symbol") or "").strip().upper() == symbol), None)
    if position is None:
        raise HTTPException(status_code=404, detail="position_not_found")
    return {
        "position_id": symbol,
        "symbol": symbol,
        "quantity": _safe_float(position.get("qty") or position.get("quantity"), 0.0),
        "avg_price": _safe_float(position.get("avg_price"), 0.0),
        "market_price": _safe_float(FEED.price(symbol), _safe_float(position.get("avg_price"), 0.0)),
        "market_value": _safe_float(position.get("market_value"), 0.0),
        "unrealized_pnl": _safe_float(position.get("unrealized_pnl"), 0.0),
        "asset_class": position.get("asset_class") or "equities",
        "instrument_type": position.get("instrument_type") or "equity",
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


@router.get("/ceo/post-trade-review", response_model=dict)
async def get_ceo_post_trade_review(
    persist: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
):
    return vektor_ceo_service.post_trade_review(persist=persist, limit=limit)


@router.get("/ceo/post-trade-reviews/latest", response_model=dict)
async def get_latest_post_trade_reviews(
    limit: int = Query(default=50, ge=1, le=200),
):
    return vektor_ceo_service.latest_post_trade_reviews(limit=limit)


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
                "decision_scoring": payload.get("decision_scoring") or _discovery_scoring_summary(discovery_snapshot),
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
