from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Any, Literal, Sequence
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_uuid() -> str:
    return str(uuid4())


def make_immutable_id(prefix: str, *parts: object) -> str:
    """
    Deterministic content-addressed ID builder for audit links.
    UUID-based model IDs remain the default integration contract.
    """
    payload = "|".join(str(part) for part in parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


class ImmutableModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Sleeve(str, Enum):
    LONG_TERM = "long_term"
    RECURRING = "recurring"
    TACTICAL = "tactical"


SLEEVE_ORDER: tuple[Sleeve, ...] = (
    Sleeve.LONG_TERM,
    Sleeve.RECURRING,
    Sleeve.TACTICAL,
)

DecisionStatus = Literal["proposed", "approved", "blocked", "executed"]
TaskStatus = Literal["queued", "running", "completed", "failed", "blocked"]


class ProvenanceRef(ImmutableModel):
    source_type: Literal["data", "research", "thesis", "risk", "execution", "allocation", "sentiment"]
    source_id: str = Field(..., min_length=3, max_length=128)


class AgentTask(ImmutableModel):
    task_id: str = Field(default_factory=_new_uuid)
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    role: str = Field(..., min_length=2, max_length=128)
    status: TaskStatus = "queued"
    priority: int = Field(default=5, ge=0, le=10)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_iso_utc_now)


class ResearchReport(ImmutableModel):
    report_id: str = Field(default_factory=_new_uuid)
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    created_at: str = Field(default_factory=_iso_utc_now)
    asset_universe: tuple[str, ...] = Field(default_factory=tuple)
    summary: str = Field(..., min_length=1, max_length=6000)
    findings: tuple[str, ...] = Field(default_factory=tuple)
    confidence: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("1"))
    provenance: tuple[ProvenanceRef, ...] = Field(default_factory=tuple)

    @field_validator("asset_universe")
    @classmethod
    def _normalize_assets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(symbol.upper() for symbol in value if symbol))


class SentimentSnapshot(ImmutableModel):
    snapshot_id: str = Field(default_factory=_new_uuid)
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    created_at: str = Field(default_factory=_iso_utc_now)
    symbol: str = Field(..., min_length=1, max_length=32)
    source: str = Field(..., min_length=2, max_length=128)
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance_url: str | None = Field(default=None, max_length=1024)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        return value.upper()


class TradeThesis(ImmutableModel):
    thesis_id: str = Field(default_factory=_new_uuid)
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    created_at: str = Field(default_factory=_iso_utc_now)
    sleeve: Sleeve
    report_ids: tuple[str, ...] = Field(..., min_length=1)
    statement: str = Field(..., min_length=1, max_length=4000)
    conviction: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("1"))


class ExecutionIntent(ImmutableModel):
    intent_id: str = Field(default_factory=_new_uuid)
    decision_id: str = Field(..., min_length=3, max_length=128)
    created_at: str = Field(default_factory=_iso_utc_now)
    sleeve: Sleeve
    symbol: str = Field(..., min_length=1, max_length=32)
    side: Literal["buy", "sell"]
    notional_usd: Decimal = Field(..., gt=Decimal("0"))
    strategy_tag: str = Field(default="core", min_length=1, max_length=128)
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        return value.upper()


class RiskAssessment(ImmutableModel):
    risk_id: str = Field(default_factory=_new_uuid)
    decision_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    created_at: str = Field(default_factory=_iso_utc_now)
    policy_version: str = Field(..., min_length=1, max_length=128)
    approved: bool
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    max_notional_usd: Decimal | None = Field(default=None, gt=Decimal("0"))


class DecisionRecord(ImmutableModel):
    decision_id: str = Field(default_factory=_new_uuid)
    run_id: str = Field(..., min_length=3, max_length=128)
    agent_id: str = Field(..., min_length=2, max_length=128)
    created_at: str = Field(default_factory=_iso_utc_now)
    sleeve: Sleeve
    thesis_id: str = Field(..., min_length=3, max_length=128)
    risk_id: str = Field(..., min_length=3, max_length=128)
    intent_id: str = Field(..., min_length=3, max_length=128)
    status: DecisionStatus = "proposed"
    provenance: tuple[ProvenanceRef, ...] = Field(default_factory=tuple)


# Backward-compatible aliases for ongoing migration work.
ResearchReportContract = ResearchReport
ThesisContract = TradeThesis
ExecutionIntentContract = ExecutionIntent
RiskGateDecisionContract = RiskAssessment
DecisionContract = DecisionRecord


def build_research_report(
    *,
    run_id: str,
    agent_id: str,
    summary: str,
    asset_universe: Sequence[str] = (),
    confidence: Decimal = Decimal("0"),
    provenance: Sequence[ProvenanceRef] = (),
) -> ResearchReport:
    return ResearchReport(
        run_id=run_id,
        agent_id=agent_id,
        summary=summary,
        asset_universe=tuple(asset_universe),
        confidence=confidence,
        provenance=tuple(provenance),
        findings=(summary,),
    )
