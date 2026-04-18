from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping
from uuid import uuid4

from app.core.context import broker as shared_broker


__all__ = ["ExecutionIntent", "PaperExecutionAdapter", "execute_approved_intent"]

_ALLOWED_SIDES = {"buy", "sell"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(frozen=True)
class TraceIds:
    """Immutable trace IDs carried from research through execution."""

    data_id: str
    research_id: str
    thesis_id: str
    decision_id: str
    risk_id: str
    intent_id: str
    execution_id: str
    run_id: str


@dataclass(frozen=True)
class ExecutionIntent:
    """Execution contract accepted by the paper adapter."""

    symbol: str
    side: str
    quantity: float
    approved: bool
    decision_id: str
    risk_id: str
    intent_id: str = field(default_factory=lambda: _new_id("intent"))
    data_id: str = field(default_factory=lambda: _new_id("data"))
    research_id: str = field(default_factory=lambda: _new_id("research"))
    thesis_id: str = field(default_factory=lambda: _new_id("thesis"))
    run_id: str = field(default_factory=lambda: _new_id("run"))
    agent_id: str = "trader"
    sleeve: str | None = None
    broker_mode: str = "paper"
    price: float | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PaperExecutionAdapter:
    """
    Paper broker adapter for approved intents.

    This adapter is deliberately paper-only and never activates live trading.
    """

    def __init__(
        self,
        broker: Any = shared_broker,
        price_lookup: Callable[[str], float] | None = None,
    ) -> None:
        self._broker = broker
        self._price_lookup = price_lookup

    def execute_intent(self, intent: ExecutionIntent) -> Dict[str, Any]:
        started_at = _utc_now_iso()
        trace = TraceIds(
            data_id=intent.data_id,
            research_id=intent.research_id,
            thesis_id=intent.thesis_id,
            decision_id=intent.decision_id,
            risk_id=intent.risk_id,
            intent_id=intent.intent_id,
            execution_id=_new_id("exec"),
            run_id=intent.run_id,
        )

        base_result = {
            "execution_id": trace.execution_id,
            "intent_id": trace.intent_id,
            "decision_id": trace.decision_id,
            "risk_id": trace.risk_id,
            "run_id": trace.run_id,
            "agent_id": intent.agent_id,
            "sleeve": intent.sleeve,
            "broker_mode": "paper",
            "started_at": started_at,
        }

        reject_reason = self._precheck(intent)
        if reject_reason:
            return {
                **base_result,
                "status": "rejected",
                "reason": reject_reason,
                "finished_at": _utc_now_iso(),
                "audit": self._build_audit(
                    intent=intent,
                    trace=trace,
                    status="rejected",
                    reason=reject_reason,
                    broker_order=None,
                    started_at=started_at,
                ),
            }

        symbol = intent.symbol.upper().strip()
        price = self._resolve_price(intent, symbol)
        if price <= 0:
            reason = "invalid_or_missing_price"
            return {
                **base_result,
                "status": "rejected",
                "reason": reason,
                "finished_at": _utc_now_iso(),
                "audit": self._build_audit(
                    intent=intent,
                    trace=trace,
                    status="rejected",
                    reason=reason,
                    broker_order=None,
                    started_at=started_at,
                ),
            }

        try:
            created = self._broker.submit_order(symbol, intent.side, intent.quantity, price)
            order_payload = {
                "id": str(getattr(created, "id", "")),
                "symbol": str(getattr(created, "symbol", symbol)),
                "side": str(getattr(created, "side", intent.side)),
                "quantity": float(getattr(created, "qty", intent.quantity)),
                "avg_price": float(getattr(created, "avg_price", price)),
                "status": str(getattr(created, "status", "filled")),
                "created_at": getattr(created, "created_at", datetime.now(timezone.utc)).isoformat(),
            }
            status = "executed"
            reason = None
        except Exception as exc:  # pragma: no cover - broker errors are runtime dependent
            order_payload = None
            status = "rejected"
            reason = f"broker_error:{exc}"

        return {
            **base_result,
            "status": status,
            "reason": reason,
            "finished_at": _utc_now_iso(),
            "order": order_payload,
            "audit": self._build_audit(
                intent=intent,
                trace=trace,
                status=status,
                reason=reason,
                broker_order=order_payload,
                started_at=started_at,
            ), 
        }

    def execute(self, raw_intent: ExecutionIntent | Mapping[str, Any]) -> Dict[str, Any]:
        """Backward-compatible entrypoint that accepts dict payloads."""

        return self.execute_intent(self._coerce_intent(raw_intent))

    def _coerce_intent(self, raw_intent: ExecutionIntent | Mapping[str, Any]) -> ExecutionIntent:
        if isinstance(raw_intent, ExecutionIntent):
            return raw_intent

        payload = dict(raw_intent)
        approved = bool(payload.get("approved") or payload.get("risk_approved"))
        return ExecutionIntent(
            symbol=str(payload.get("symbol", "")).upper(),
            side=str(payload.get("side", "")).lower(),
            quantity=float(payload.get("quantity", payload.get("qty", 0.0)) or 0.0),
            approved=approved,
            decision_id=str(payload.get("decision_id") or _new_id("decision")),
            risk_id=str(payload.get("risk_id") or _new_id("risk")),
            intent_id=str(payload.get("intent_id") or _new_id("intent")),
            data_id=str(payload.get("data_id") or _new_id("data")),
            research_id=str(payload.get("research_id") or _new_id("research")),
            thesis_id=str(payload.get("thesis_id") or _new_id("thesis")),
            run_id=str(payload.get("run_id") or _new_id("run")),
            agent_id=str(payload.get("agent_id") or "trader"),
            sleeve=payload.get("sleeve"),
            broker_mode=str(payload.get("broker_mode") or "paper").lower(),
            price=float(payload["price"]) if payload.get("price") is not None else None,
            metadata=dict(payload.get("metadata") or {}),
        )

    def _precheck(self, intent: ExecutionIntent) -> str | None:
        if not intent.approved:
            return "intent_not_approved"
        if intent.broker_mode != "paper":
            return "live_trading_disabled"
        if intent.side not in _ALLOWED_SIDES:
            return "invalid_side"
        if intent.quantity <= 0:
            return "invalid_quantity"
        if not intent.symbol:
            return "missing_symbol"
        return None

    def _resolve_price(self, intent: ExecutionIntent, symbol: str) -> float:
        if intent.price is not None:
            return float(intent.price)
        if self._price_lookup is not None:
            return float(self._price_lookup(symbol))
        return 0.0

    def _build_audit(
        self,
        *,
        intent: ExecutionIntent,
        trace: TraceIds,
        status: str,
        reason: str | None,
        broker_order: Dict[str, Any] | None,
        started_at: str,
    ) -> Dict[str, Any]:
        return {
            "event_id": _new_id("audit"),
            "event_type": "execution_intent_processed",
            "status": status,
            "reason": reason,
            "occurred_at": _utc_now_iso(),
            "started_at": started_at,
            "trace": asdict(trace),
            "intent": {
                "symbol": intent.symbol,
                "side": intent.side,
                "quantity": intent.quantity,
                "approved": intent.approved,
                "broker_mode": intent.broker_mode,
                "agent_id": intent.agent_id,
                "sleeve": intent.sleeve,
                "metadata": intent.metadata,
            },
            "broker_order": broker_order,
        }


def execute_approved_intent(
    raw_intent: ExecutionIntent | Mapping[str, Any],
    *,
    price_lookup: Callable[[str], float] | None = None,
    broker: Any = shared_broker,
) -> Dict[str, Any]:
    """Functional wrapper used by orchestration callers."""

    return PaperExecutionAdapter(broker=broker, price_lookup=price_lookup).execute(raw_intent)
