from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List, Tuple

from app.fund.execution_adapter import ExecutionIntent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class PolicyLimits:
    max_open_positions: int = 8
    max_order_notional_usd: float = 25_000.0
    max_symbol_exposure_pct: float = 0.30
    max_position_notional_pct: float = 0.20


class PolicyGate:
    """
    Mandatory pre-trade policy checks.

    Integration contract:
    evaluate(intent: ExecutionIntent, positions: list[dict], equity: float)
      -> tuple[bool, list[str]]
    """

    def __init__(self, limits: PolicyLimits | None = None) -> None:
        self._limits = limits or PolicyLimits()
        self._lock = RLock()
        self._evaluations: List[Dict[str, object]] = []

    def evaluate(
        self,
        intent: ExecutionIntent,
        positions: List[dict],
        equity: float,
    ) -> Tuple[bool, List[str]]:
        blocked: List[str] = []

        if not intent.approved:
            blocked.append("intent_not_approved")
        if intent.broker_mode != "paper":
            blocked.append("live_trading_disabled")
        if not intent.symbol or not intent.symbol.strip():
            blocked.append("missing_symbol")
        if not intent.decision_id or not intent.decision_id.strip():
            blocked.append("missing_decision_id")
        if not intent.risk_id or not intent.risk_id.strip():
            blocked.append("missing_risk_id")
        if not intent.run_id or not intent.run_id.strip():
            blocked.append("missing_run_id")
        if not intent.agent_id or not intent.agent_id.strip():
            blocked.append("missing_agent_id")
        if intent.side not in {"buy", "sell"}:
            blocked.append("invalid_side")
        if intent.quantity <= 0:
            blocked.append("invalid_quantity")
        if equity <= 0:
            blocked.append("invalid_equity")

        price = self._resolve_price(intent)
        notional = intent.quantity * price
        if price <= 0:
            blocked.append("missing_or_invalid_price")
        if notional <= 0:
            blocked.append("invalid_notional")
        elif notional > self._limits.max_order_notional_usd:
            blocked.append("order_notional_limit_exceeded")

        open_positions = [p for p in positions if _safe_float(p.get("qty", 0.0)) > 0]
        open_symbols = {str(p.get("symbol", "")).upper() for p in open_positions}
        symbol = intent.symbol.upper().strip()
        if intent.side == "buy" and symbol not in open_symbols and len(open_symbols) >= self._limits.max_open_positions:
            blocked.append("max_open_positions_exceeded")

        if equity > 0 and price > 0 and symbol:
            symbol_exposure = self._symbol_exposure(symbol, open_positions)
            if intent.side == "buy":
                projected = symbol_exposure + notional
            else:
                projected = max(0.0, symbol_exposure - notional)
            concentration = projected / equity
            if concentration > self._limits.max_symbol_exposure_pct:
                blocked.append("symbol_exposure_limit_exceeded")

            if notional / equity > self._limits.max_position_notional_pct:
                blocked.append("single_position_notional_limit_exceeded")

        if isinstance(intent.metadata, dict):
            if "available_cash" in intent.metadata:
                available_cash = _safe_float(intent.metadata.get("available_cash"))
                if intent.side == "buy" and notional > available_cash:
                    blocked.append("insufficient_cash")

            sleeve = intent.metadata.get("sleeve")
            if sleeve is not None and str(sleeve).strip() == "":
                blocked.append("invalid_sleeve")

            if intent.metadata.get("direct_execution") is True:
                blocked.append("direct_execution_not_permitted")

        blocked = list(dict.fromkeys(blocked))
        approved = len(blocked) == 0
        self._record_evaluation(intent=intent, equity=equity, blocked=blocked, approved=approved, notional=notional)
        return approved, blocked

    def list_evaluations(self, limit: int = 100) -> List[Dict[str, object]]:
        with self._lock:
            items = list(self._evaluations)
        return items[-limit:] if limit >= 0 else items

    def list_blocked(self, limit: int = 100) -> List[Dict[str, object]]:
        blocked = [item for item in self.list_evaluations(limit=10_000) if not bool(item.get("approved"))]
        return blocked[-limit:] if limit >= 0 else blocked

    @property
    def limits(self) -> PolicyLimits:
        return self._limits

    def _resolve_price(self, intent: ExecutionIntent) -> float:
        if intent.price is not None:
            return float(intent.price)
        if isinstance(intent.metadata, dict):
            return _safe_float(intent.metadata.get("price") or intent.metadata.get("reference_price"))
        return 0.0

    def _symbol_exposure(self, symbol: str, positions: List[dict]) -> float:
        total = 0.0
        for position in positions:
            if str(position.get("symbol", "")).upper() != symbol:
                continue
            market_value = _safe_float(position.get("market_value"))
            if market_value > 0:
                total += market_value
                continue
            qty = _safe_float(position.get("qty"))
            px = _safe_float(position.get("market_price"))
            total += max(0.0, qty * px)
        return total

    def _record_evaluation(
        self,
        *,
        intent: ExecutionIntent,
        equity: float,
        blocked: List[str],
        approved: bool,
        notional: float,
    ) -> None:
        record = {
            "evaluated_at": _utc_now().isoformat(),
            "decision_id": intent.decision_id,
            "risk_id": intent.risk_id,
            "intent_id": intent.intent_id,
            "run_id": intent.run_id,
            "agent_id": intent.agent_id,
            "symbol": intent.symbol,
            "side": intent.side,
            "quantity": float(intent.quantity),
            "notional": float(notional),
            "equity": float(equity),
            "approved": approved,
            "blocked_reasons": list(blocked),
        }
        with self._lock:
            self._evaluations.append(record)


policy_gate = PolicyGate()
