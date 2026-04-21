from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping
from uuid import uuid4

import requests

from app.config import get_settings
from app.core.context import broker as shared_broker
from app.fund.allocation_policy import (
    infer_asset_class,
    infer_instrument_type,
    infer_routing_mode,
    infer_underlier_symbol,
)


__all__ = [
    "ExecutionIntent",
    "PaperExecutionAdapter",
    "execute_approved_intent",
]

_ALLOWED_SIDES = {"buy", "sell"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


@dataclass(frozen=True)
class TraceIds:
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
    asset_class: str = "equities"
    instrument_type: str = "equity"
    routing_mode: str = "paper_equity"
    underlier_symbol: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PaperVenueAdapter:
    routing_modes: tuple[str, ...] = ()
    instrument_type: str = "equity"
    contract_multiplier: float = 1.0
    live_supported: bool = False

    def supports(self, intent: ExecutionIntent) -> bool:
        return intent.routing_mode in self.routing_modes

    def precheck(self, intent: ExecutionIntent) -> str | None:
        if not intent.approved:
            return "intent_not_approved"
        if intent.side not in _ALLOWED_SIDES:
            return "invalid_side"
        if intent.quantity <= 0:
            return "invalid_quantity"
        if not intent.symbol:
            return "missing_symbol"
        if intent.broker_mode != "paper":
            return "live_trading_disabled" if not self.live_supported else None
        return None

    def effective_price(self, *, intent: ExecutionIntent, price: float) -> float:
        return float(price)

    def cash_notional(self, *, intent: ExecutionIntent, price: float) -> float:
        return float(intent.quantity) * float(price) * float(self.contract_multiplier)

    def position_metadata(self, intent: ExecutionIntent) -> Dict[str, Any]:
        return {
            "asset_class": intent.asset_class,
            "instrument_type": intent.instrument_type or self.instrument_type,
            "routing_mode": intent.routing_mode,
            "underlier_symbol": intent.underlier_symbol,
            "contract_multiplier": self.contract_multiplier,
            "metadata": dict(intent.metadata or {}),
        }

    def submit(self, broker: Any, *, intent: ExecutionIntent, price: float) -> Any:
        return broker.submit_order(
            intent.symbol,
            intent.side,
            intent.quantity,
            price,
            asset_class=intent.asset_class,
            instrument_type=intent.instrument_type or self.instrument_type,
            routing_mode=intent.routing_mode,
            underlier_symbol=intent.underlier_symbol,
            contract_multiplier=self.contract_multiplier,
            metadata=dict(intent.metadata or {}),
        )


class AlpacaTradingVenueAdapter:
    live_supported = True
    supported_routes = {"paper_equity", "paper_equity_proxy", "paper_crypto", "paper_options"}

    def __init__(self) -> None:
        self._settings = get_settings()

    def supports(self, intent: ExecutionIntent) -> bool:
        return intent.routing_mode in self.supported_routes

    def precheck(self, intent: ExecutionIntent) -> str | None:
        if not intent.approved:
            return "intent_not_approved"
        if not self._settings.LIVE_TRADING_ENABLED:
            return "live_trading_disabled"
        if not self._settings.ALPACA_API_KEY or not self._settings.ALPACA_SECRET_KEY:
            return "alpaca_credentials_missing"
        if intent.side not in _ALLOWED_SIDES:
            return "invalid_side"
        if intent.quantity <= 0:
            return "invalid_quantity"
        if not self.supports(intent):
            return f"unsupported_execution_route:{intent.routing_mode}"
        return None

    def submit(self, *, intent: ExecutionIntent) -> dict[str, Any]:
        base_url = self._settings.ALPACA_LIVE_BASE_URL if intent.broker_mode == "live" else self._settings.ALPACA_BASE_URL
        headers = {
            "APCA-API-KEY-ID": str(self._settings.ALPACA_API_KEY or ""),
            "APCA-API-SECRET-KEY": str(self._settings.ALPACA_SECRET_KEY or ""),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        tif = "gtc" if intent.asset_class == "crypto" else "day"
        payload: dict[str, Any] = {
            "symbol": intent.symbol,
            "side": intent.side,
            "type": "market",
            "time_in_force": tif,
        }
        if float(intent.quantity).is_integer():
            payload["qty"] = int(intent.quantity)
        else:
            payload["qty"] = float(intent.quantity)
        if intent.asset_class == "options":
            payload["order_class"] = "simple"
        response = requests.post(
            f"{base_url.rstrip('/')}/v2/orders",
            json=payload,
            headers=headers,
            timeout=float(self._settings.ALPACA_HTTP_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        body = response.json()
        return {
            "id": str(body.get("id") or ""),
            "symbol": str(body.get("symbol") or intent.symbol),
            "side": str(body.get("side") or intent.side),
            "quantity": _safe_float(body.get("qty"), intent.quantity),
            "avg_price": _safe_float(body.get("filled_avg_price"), intent.price or 0.0),
            "status": str(body.get("status") or "accepted"),
            "created_at": str(body.get("created_at") or _utc_now_iso()),
            "raw": body,
        }


class OandaForexVenueAdapter:
    live_supported = True
    supported_routes = {"paper_forex"}

    def __init__(self) -> None:
        self._settings = get_settings()

    def supports(self, intent: ExecutionIntent) -> bool:
        return intent.routing_mode in self.supported_routes and intent.asset_class == "forex"

    def precheck(self, intent: ExecutionIntent) -> str | None:
        if not intent.approved:
            return "intent_not_approved"
        if not self._settings.LIVE_TRADING_ENABLED:
            return "live_trading_disabled"
        if not self._settings.OANDA_API_TOKEN or not self._settings.OANDA_ACCOUNT_ID:
            return "oanda_credentials_missing"
        if intent.side not in _ALLOWED_SIDES:
            return "invalid_side"
        if intent.quantity <= 0:
            return "invalid_quantity"
        if "/" not in intent.symbol:
            return "invalid_forex_symbol"
        return None

    def submit(self, *, intent: ExecutionIntent) -> dict[str, Any]:
        base_url = self._settings.OANDA_LIVE_BASE_URL if intent.broker_mode == "live" else self._settings.OANDA_BASE_URL
        units = int(abs(intent.quantity))
        if intent.side == "sell":
            units = -units
        instrument = intent.symbol.upper().replace("/", "_")
        payload = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        response = requests.post(
            f"{base_url.rstrip('/')}/v3/accounts/{self._settings.OANDA_ACCOUNT_ID}/orders",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._settings.OANDA_API_TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=float(self._settings.OANDA_HTTP_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        body = response.json()
        txn = body.get("orderFillTransaction") or body.get("orderCreateTransaction") or {}
        price = _safe_float(txn.get("price"), intent.price or 0.0)
        return {
            "id": str(txn.get("id") or body.get("lastTransactionID") or ""),
            "symbol": intent.symbol,
            "side": intent.side,
            "quantity": abs(_safe_float(txn.get("units"), intent.quantity)),
            "avg_price": price,
            "status": "filled" if body.get("orderFillTransaction") else "accepted",
            "created_at": str(txn.get("time") or _utc_now_iso()),
            "raw": body,
        }


class EquityPaperAdapter(PaperVenueAdapter):
    routing_modes = ("paper_equity", "paper_equity_proxy")
    instrument_type = "equity"
    contract_multiplier = 1.0


class CryptoPaperAdapter(PaperVenueAdapter):
    routing_modes = ("paper_crypto",)
    instrument_type = "crypto_spot"
    contract_multiplier = 1.0

    def precheck(self, intent: ExecutionIntent) -> str | None:
        reason = super().precheck(intent)
        if reason:
            return reason
        if "-" not in intent.symbol:
            return "invalid_crypto_symbol"
        return None


class ForexPaperAdapter(PaperVenueAdapter):
    routing_modes = ("paper_forex",)
    instrument_type = "fx_spot"
    contract_multiplier = 1.0

    def precheck(self, intent: ExecutionIntent) -> str | None:
        reason = super().precheck(intent)
        if reason:
            return reason
        symbol = intent.symbol.upper().strip()
        if "/" not in symbol or len(symbol.replace("/", "")) < 6:
            return "invalid_forex_symbol"
        base, quote = symbol.split("/", 1)
        if not base or not quote:
            return "invalid_forex_symbol"
        if quote != "USD":
            return "paper_forex_requires_usd_quote"
        return None


class OptionsPaperAdapter(PaperVenueAdapter):
    routing_modes = ("paper_options",)
    instrument_type = "option_contract"
    contract_multiplier = 100.0

    def precheck(self, intent: ExecutionIntent) -> str | None:
        reason = super().precheck(intent)
        if reason:
            return reason
        if not intent.underlier_symbol:
            return "missing_option_underlier"
        return None


class PaperExecutionAdapter:
    """
    Paper broker adapter for approved intents.

    Supports dedicated paper routes for equities, commodity ETF proxies, crypto,
    spot FX, and listed options. Live trading remains disabled.
    """

    def __init__(
        self,
        broker: Any = shared_broker,
        price_lookup: Callable[[str], float] | None = None,
    ) -> None:
        self._broker = broker
        self._price_lookup = price_lookup
        self._settings = get_settings()
        adapters = (
            EquityPaperAdapter(),
            CryptoPaperAdapter(),
            ForexPaperAdapter(),
            OptionsPaperAdapter(),
        )
        self._adapters = {route: adapter for adapter in adapters for route in adapter.routing_modes}
        self._live_adapters = (
            AlpacaTradingVenueAdapter(),
            OandaForexVenueAdapter(),
        )

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
            "asset_class": intent.asset_class,
            "instrument_type": intent.instrument_type,
            "routing_mode": intent.routing_mode,
        }

        live_mode = str(intent.broker_mode or "paper").lower() == "live"
        adapter = self._select_adapter(intent, live_mode=live_mode)
        if adapter is None:
            reason = f"unsupported_execution_route:{intent.routing_mode}"
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

        reject_reason = adapter.precheck(intent)
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

        effective_price = adapter.effective_price(intent=intent, price=price) if hasattr(adapter, "effective_price") else float(price)
        notional = adapter.cash_notional(intent=intent, price=effective_price) if hasattr(adapter, "cash_notional") else float(intent.quantity) * float(effective_price)

        try:
            if live_mode:
                created = adapter.submit(intent=intent)
            else:
                created = adapter.submit(self._broker, intent=intent, price=effective_price)
            order_payload = self._normalize_order_payload(
                created=created,
                intent=intent,
                fallback_symbol=symbol,
                fallback_price=effective_price,
                notional=notional,
            )
            status = "executed"
            reason = None
        except Exception as exc:  # pragma: no cover
            order_payload = None
            status = "rejected"
            reason = f"broker_error:{exc}"

        return {
            **base_result,
            "status": status,
            "reason": reason,
            "finished_at": _utc_now_iso(),
            "cash_notional": float(notional),
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
        return self.execute_intent(self._coerce_intent(raw_intent))

    def _select_adapter(self, intent: ExecutionIntent, *, live_mode: bool) -> Any | None:
        if live_mode:
            for adapter in self._live_adapters:
                if adapter.supports(intent):
                    return adapter
            return None
        return self._adapters.get(intent.routing_mode)

    def _coerce_intent(self, raw_intent: ExecutionIntent | Mapping[str, Any]) -> ExecutionIntent:
        if isinstance(raw_intent, ExecutionIntent):
            return raw_intent

        payload = dict(raw_intent)
        metadata = dict(payload.get("metadata") or {})
        asset_class = payload.get("asset_class") or metadata.get("asset_class")
        approved = bool(payload.get("approved") or payload.get("risk_approved"))
        symbol = str(payload.get("symbol", "")).upper()
        resolved_asset_class = str(asset_class or infer_asset_class(symbol))
        return ExecutionIntent(
            symbol=symbol,
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
            asset_class=resolved_asset_class,
            instrument_type=str(
                payload.get("instrument_type")
                or metadata.get("instrument_type")
                or infer_instrument_type(symbol, resolved_asset_class)
            ),
            routing_mode=str(
                payload.get("routing_mode")
                or metadata.get("routing_mode")
                or infer_routing_mode(symbol, resolved_asset_class)
            ),
            underlier_symbol=payload.get("underlier_symbol")
            or metadata.get("underlier_symbol")
            or infer_underlier_symbol(symbol, resolved_asset_class),
            metadata=metadata,
        )

    def _resolve_price(self, intent: ExecutionIntent, symbol: str) -> float:
        if intent.price is not None:
            return float(intent.price)
        if self._price_lookup is not None:
            return float(self._price_lookup(symbol))
        return 0.0

    def _normalize_order_payload(
        self,
        *,
        created: Any,
        intent: ExecutionIntent,
        fallback_symbol: str,
        fallback_price: float,
        notional: float,
    ) -> Dict[str, Any]:
        if isinstance(created, Mapping):
            created_at = str(created.get("created_at") or _utc_now_iso())
            return {
                "id": str(created.get("id") or ""),
                "symbol": str(created.get("symbol") or fallback_symbol),
                "side": str(created.get("side") or intent.side),
                "quantity": _safe_float(created.get("quantity"), intent.quantity),
                "avg_price": _safe_float(created.get("avg_price"), fallback_price),
                "status": str(created.get("status") or "filled"),
                "created_at": created_at,
                "asset_class": intent.asset_class,
                "instrument_type": intent.instrument_type,
                "routing_mode": intent.routing_mode,
                "underlier_symbol": intent.underlier_symbol,
                "cash_notional": float(notional),
                "raw": created.get("raw"),
            }
        return {
            "id": str(getattr(created, "id", "")),
            "symbol": str(getattr(created, "symbol", fallback_symbol)),
            "side": str(getattr(created, "side", intent.side)),
            "quantity": float(getattr(created, "qty", intent.quantity)),
            "avg_price": float(getattr(created, "avg_price", fallback_price)),
            "status": str(getattr(created, "status", "filled")),
            "created_at": getattr(created, "created_at", datetime.now(timezone.utc)).isoformat(),
            "asset_class": intent.asset_class,
            "instrument_type": intent.instrument_type,
            "routing_mode": intent.routing_mode,
            "underlier_symbol": intent.underlier_symbol,
            "cash_notional": float(notional),
        }

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
                "asset_class": intent.asset_class,
                "instrument_type": intent.instrument_type,
                "routing_mode": intent.routing_mode,
                "underlier_symbol": intent.underlier_symbol,
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
    return PaperExecutionAdapter(broker=broker, price_lookup=price_lookup).execute(raw_intent)
