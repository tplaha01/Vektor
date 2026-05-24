from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Tuple

from app.config import get_settings
from app.fund.core_engine_scoring import resolve_decision_scoring
from app.fund.execution_adapter import ExecutionIntent
from app.quant.risk import infer_portfolio_risk_regime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _symbol_group(symbol: str, asset_class: str, metadata: dict[str, object] | None = None) -> str:
    meta = metadata if isinstance(metadata, dict) else {}
    explicit = str(meta.get("correlation_group") or "").strip().lower()
    if explicit:
        return explicit
    normalized_symbol = str(symbol or "").upper().strip()
    if asset_class == "forex":
        return "fx_usd"
    if asset_class == "crypto":
        return "crypto_beta"
    if asset_class == "commodities":
        return "commodity_macro"
    if normalized_symbol in {"SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMD", "AMZN", "GOOGL", "META", "TSLA", "XLK"}:
        return "equity_growth"
    if normalized_symbol in {"XLF", "JPM", "BAC", "GS"}:
        return "equity_financials"
    if normalized_symbol in {"XLE", "USO", "UNG", "GLD", "SLV"}:
        return "commodity_macro"
    if normalized_symbol in {"TLT", "IEF", "SHY"}:
        return "rates_duration"
    return f"{asset_class}_general"


@dataclass(frozen=True)
class PolicyLimits:
    max_open_positions: int = 8
    max_order_notional_usd: float = 25_000.0
    max_symbol_exposure_pct: float = 0.30
    max_position_notional_pct: float = 0.20


@dataclass(frozen=True)
class DecisionGateThresholdProfile:
    min_score: float
    min_confidence: float
    min_regime_alignment: float
    min_liquidity_score: float
    max_news_intensity_count: int
    applied_profiles: tuple[str, ...] = ()
    adjustment_reasons: tuple[str, ...] = ()
    portfolio_context: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "min_score": round(float(self.min_score), 4),
            "min_confidence": round(float(self.min_confidence), 4),
            "min_regime_alignment": round(float(self.min_regime_alignment), 4),
            "min_liquidity_score": round(float(self.min_liquidity_score), 4),
            "max_news_intensity_count": int(self.max_news_intensity_count),
            "applied_profiles": list(self.applied_profiles),
            "adjustment_reasons": list(self.adjustment_reasons),
            "portfolio_context": dict(self.portfolio_context or {}),
        }


def _normalize_profile_key(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _parse_profile_map(raw: object) -> dict[str, dict[str, object]]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {
            _normalize_profile_key(key): value
            for key, value in raw.items()
            if isinstance(value, dict)
        }
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        _normalize_profile_key(key): value
        for key, value in parsed.items()
        if isinstance(value, dict)
    }


def _coerce_thresholds(
    base: DecisionGateThresholdProfile,
    override: dict[str, object],
    label: str,
) -> DecisionGateThresholdProfile:
    if not override:
        return base
    return DecisionGateThresholdProfile(
        min_score=_safe_float(override.get("min_score")) or base.min_score,
        min_confidence=_safe_float(override.get("min_confidence")) or base.min_confidence,
        min_regime_alignment=_safe_float(override.get("min_regime_alignment")) or base.min_regime_alignment,
        min_liquidity_score=_safe_float(override.get("min_liquidity_score")) or base.min_liquidity_score,
        max_news_intensity_count=int(_safe_float(override.get("max_news_intensity_count")) or base.max_news_intensity_count),
        applied_profiles=(*base.applied_profiles, label),
        adjustment_reasons=base.adjustment_reasons,
        portfolio_context=base.portfolio_context,
    )


def _with_adjustment(
    base: DecisionGateThresholdProfile,
    *,
    label: str,
    min_score_delta: float = 0.0,
    min_confidence_delta: float = 0.0,
    min_regime_alignment_delta: float = 0.0,
    min_liquidity_score_delta: float = 0.0,
    max_news_delta: int = 0,
) -> DecisionGateThresholdProfile:
    return DecisionGateThresholdProfile(
        min_score=round(base.min_score + min_score_delta, 4),
        min_confidence=round(base.min_confidence + min_confidence_delta, 4),
        min_regime_alignment=round(base.min_regime_alignment + min_regime_alignment_delta, 4),
        min_liquidity_score=round(base.min_liquidity_score + min_liquidity_score_delta, 4),
        max_news_intensity_count=max(1, int(base.max_news_intensity_count + max_news_delta)),
        applied_profiles=base.applied_profiles,
        adjustment_reasons=(*base.adjustment_reasons, label),
        portfolio_context=base.portfolio_context,
    )


def build_portfolio_threshold_context(
    *,
    symbol: str,
    asset_class: str,
    positions: list[dict[str, object]],
    equity: float,
    notional: float,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    meta = metadata if isinstance(metadata, dict) else {}
    risk_snapshot = infer_portfolio_risk_regime(
        symbol=symbol,
        asset_class=asset_class,
        positions=positions,
        equity=equity,
        notional=notional,
        metadata=meta,
    )
    return {
        **risk_snapshot.to_dict(),
        "event_risk_active": bool(meta.get("event_risk_active", False)),
        "correlation_group": _symbol_group(str(symbol or "").upper().strip(), str(asset_class or "").strip().lower(), meta),
    }


def resolve_decision_gate_thresholds(
    settings: Any | None = None,
    *,
    asset_class: str | None = None,
    strategy_family: str | None = None,
    portfolio_context: dict[str, object] | None = None,
) -> DecisionGateThresholdProfile:
    resolved_settings = settings or get_settings()
    profile = DecisionGateThresholdProfile(
        min_score=float(resolved_settings.DECISION_GATE_MIN_SCORE),
        min_confidence=float(resolved_settings.DECISION_GATE_MIN_CONFIDENCE),
        min_regime_alignment=float(resolved_settings.DECISION_GATE_MIN_REGIME_ALIGNMENT),
        min_liquidity_score=float(resolved_settings.DECISION_GATE_MIN_LIQUIDITY_SCORE),
        max_news_intensity_count=int(resolved_settings.DECISION_GATE_MAX_NEWS_INTENSITY_COUNT),
        applied_profiles=("default",),
        portfolio_context=dict(portfolio_context or {}),
    )
    normalized_asset_class = _normalize_profile_key(asset_class)
    normalized_strategy_family = _normalize_profile_key(strategy_family)
    asset_profiles = _parse_profile_map(getattr(resolved_settings, "DECISION_GATE_ASSET_CLASS_PROFILES", ""))
    strategy_profiles = _parse_profile_map(getattr(resolved_settings, "DECISION_GATE_STRATEGY_FAMILY_PROFILES", ""))
    combo_profiles = _parse_profile_map(getattr(resolved_settings, "DECISION_GATE_ASSET_STRATEGY_PROFILES", ""))

    if normalized_asset_class and normalized_asset_class in asset_profiles:
        profile = _coerce_thresholds(profile, asset_profiles[normalized_asset_class], f"asset_class:{normalized_asset_class}")
    if normalized_strategy_family and normalized_strategy_family in strategy_profiles:
        profile = _coerce_thresholds(profile, strategy_profiles[normalized_strategy_family], f"strategy_family:{normalized_strategy_family}")
    combo_key = f"{normalized_asset_class}:{normalized_strategy_family}" if normalized_asset_class and normalized_strategy_family else ""
    if combo_key and combo_key in combo_profiles:
        profile = _coerce_thresholds(profile, combo_profiles[combo_key], f"asset_strategy:{combo_key}")
    context = dict(portfolio_context or {})
    macro_risk_level = str(context.get("macro_risk_level") or "").strip().lower()
    symbol_exposure_ratio = _safe_float(context.get("symbol_exposure_ratio"))
    correlated_group_exposure_ratio = _safe_float(context.get("correlated_group_exposure_ratio"))
    asset_class_usage_ratio = _safe_float(context.get("asset_class_usage_ratio"))
    cash_reserve_ratio = _safe_float(context.get("cash_reserve_ratio"))
    min_cash_reserve_ratio = _safe_float(context.get("min_cash_reserve_ratio"))

    if macro_risk_level in {"risk_off", "stressed", "volatile"}:
        profile = _with_adjustment(
            profile,
            label=f"portfolio:macro_risk:{macro_risk_level}",
            min_score_delta=0.03,
            min_confidence_delta=0.04,
            min_regime_alignment_delta=0.05,
            max_news_delta=-2,
        )
    if symbol_exposure_ratio >= 0.22:
        profile = _with_adjustment(
            profile,
            label="portfolio:symbol_concentration_high",
            min_score_delta=0.04,
            min_confidence_delta=0.03,
            min_regime_alignment_delta=0.03,
        )
    elif symbol_exposure_ratio >= 0.15:
        profile = _with_adjustment(
            profile,
            label="portfolio:symbol_concentration_elevated",
            min_score_delta=0.02,
            min_confidence_delta=0.02,
            min_regime_alignment_delta=0.02,
        )
    if correlated_group_exposure_ratio >= 0.30:
        profile = _with_adjustment(
            profile,
            label="portfolio:correlated_group_high",
            min_score_delta=0.03,
            min_confidence_delta=0.02,
            min_regime_alignment_delta=0.03,
        )
    elif correlated_group_exposure_ratio >= 0.22:
        profile = _with_adjustment(
            profile,
            label="portfolio:correlated_group_elevated",
            min_score_delta=0.015,
            min_confidence_delta=0.015,
            min_regime_alignment_delta=0.02,
        )
    if asset_class_usage_ratio >= 0.9:
        profile = _with_adjustment(
            profile,
            label="portfolio:asset_budget_near_full",
            min_score_delta=0.025,
            min_confidence_delta=0.02,
            min_liquidity_score_delta=0.03,
        )
    elif asset_class_usage_ratio >= 0.75:
        profile = _with_adjustment(
            profile,
            label="portfolio:asset_budget_tight",
            min_score_delta=0.015,
            min_confidence_delta=0.01,
            min_liquidity_score_delta=0.02,
        )
    if min_cash_reserve_ratio > 0 and cash_reserve_ratio < min_cash_reserve_ratio:
        profile = _with_adjustment(
            profile,
            label="portfolio:cash_reserve_breach_risk",
            min_score_delta=0.03,
            min_confidence_delta=0.02,
            min_liquidity_score_delta=0.05,
        )
    elif min_cash_reserve_ratio > 0 and cash_reserve_ratio < (min_cash_reserve_ratio + 0.05):
        profile = _with_adjustment(
            profile,
            label="portfolio:cash_reserve_tight",
            min_score_delta=0.015,
            min_liquidity_score_delta=0.03,
        )
    return profile


class PolicyGate:
    """
    Mandatory pre-trade policy checks.

    Integration contract:
    evaluate(intent: ExecutionIntent, positions: list[dict], equity: float)
      -> tuple[bool, list[str]]
    """

    def __init__(self, limits: PolicyLimits | None = None) -> None:
        self._limits = limits or PolicyLimits()
        self._settings = get_settings()
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

            # This limit is intended to cap sizing on new/additive risk.
            # Sells reduce exposure and should not be blocked by this check.
            if intent.side == "buy" and (notional / equity > self._limits.max_position_notional_pct):
                blocked.append("single_position_notional_limit_exceeded")

        if isinstance(intent.metadata, dict):
            constraints = intent.metadata.get("allocation_constraints")
            asset_class = str(intent.metadata.get("asset_class") or intent.asset_class or "").strip().lower()
            routing_mode = str(intent.metadata.get("routing_mode") or intent.routing_mode or "").strip().lower()
            instrument_type = str(intent.metadata.get("instrument_type") or intent.instrument_type or "").strip().lower()
            correlation_group = _symbol_group(intent.symbol, asset_class, intent.metadata)

            if "available_cash" in intent.metadata:
                available_cash = _safe_float(intent.metadata.get("available_cash"))
                if intent.side == "buy" and notional > available_cash:
                    blocked.append("insufficient_cash")

            remaining_budget = _safe_float(intent.metadata.get("sleeve_budget_remaining_usd"))
            allocated_budget = _safe_float(intent.metadata.get("sleeve_budget_allocated_usd"))
            if intent.side == "buy" and allocated_budget > 0 and notional > remaining_budget:
                blocked.append("sleeve_budget_exceeded")

            sleeve = intent.metadata.get("sleeve")
            if sleeve is not None and str(sleeve).strip() == "":
                blocked.append("invalid_sleeve")

            if intent.metadata.get("direct_execution") is True:
                blocked.append("direct_execution_not_permitted")

            if isinstance(constraints, dict):
                allowed_asset_classes = constraints.get("allowed_asset_classes")
                if isinstance(allowed_asset_classes, list) and asset_class:
                    allowed = {str(item).strip().lower() for item in allowed_asset_classes if str(item).strip()}
                    if allowed and asset_class not in allowed:
                        blocked.append("asset_class_not_allocated")
                if intent.side == "buy" and asset_class:
                    asset_class_remaining = _safe_float(intent.metadata.get("asset_class_budget_remaining_usd"))
                    asset_class_allocated = _safe_float(intent.metadata.get("asset_class_budget_allocated_usd"))
                    if asset_class_allocated > 0 and notional > asset_class_remaining:
                        blocked.append("asset_class_budget_exceeded")
                max_asset_class_exposure_pct = _safe_float(constraints.get("max_asset_class_exposure_pct"))
                asset_class_used_usd = _safe_float(intent.metadata.get("asset_class_budget_used_usd"))
                if (
                    intent.side == "buy"
                    and equity > 0
                    and max_asset_class_exposure_pct > 0
                    and ((asset_class_used_usd + notional) / equity) > max_asset_class_exposure_pct
                ):
                    blocked.append("asset_class_exposure_limit_exceeded")
                cash_hold_enabled = bool(constraints.get("cash_hold_enabled", True))
                if cash_hold_enabled and intent.side == "buy":
                    min_cash_reserve_pct = _safe_float(constraints.get("min_cash_reserve_pct"))
                    if min_cash_reserve_pct > 0:
                        post_trade_cash = _safe_float(intent.metadata.get("available_cash")) - notional
                        minimum_cash = equity * min_cash_reserve_pct
                        if post_trade_cash < minimum_cash:
                            blocked.append("cash_reserve_floor_breached")
                if bool(constraints.get("risk_off_mode_enabled", False)) and intent.side == "buy":
                    macro_risk_level = str(intent.metadata.get("macro_risk_level") or "").strip().lower()
                    if macro_risk_level in {"risk_off", "stressed", "volatile"}:
                        blocked.append("risk_off_regime_block")
                if bool(constraints.get("thesis_invalidation_required", False)):
                    thesis_state = str(intent.metadata.get("thesis_state") or "valid").strip().lower()
                    if thesis_state in {"degraded", "broken"}:
                        blocked.append(f"thesis_{thesis_state}")
                if bool(constraints.get("event_risk_news_threshold")) and intent.side == "buy":
                    news_count = _safe_float(intent.metadata.get("news_intensity_count"))
                    if news_count >= _safe_float(constraints.get("event_risk_news_threshold")) and bool(intent.metadata.get("event_risk_active", True)):
                        blocked.append("event_risk_gate")
                max_correlated_group_exposure_pct = _safe_float(constraints.get("max_correlated_group_exposure_pct"))
                if intent.side == "buy" and equity > 0 and max_correlated_group_exposure_pct > 0:
                    current_group_exposure = 0.0
                    for position in open_positions:
                        position_meta = position.get("metadata") if isinstance(position.get("metadata"), dict) else {}
                        position_asset_class = str(position.get("asset_class") or "equities").strip().lower()
                        group = _symbol_group(str(position.get("symbol") or ""), position_asset_class, position_meta)
                        if group != correlation_group:
                            continue
                        current_group_exposure += max(
                            _safe_float(position.get("market_value")),
                            _safe_float(position.get("qty")) * _safe_float(position.get("market_price")),
                        )
                    if ((current_group_exposure + notional) / equity) > max_correlated_group_exposure_pct:
                        blocked.append("correlated_group_exposure_limit_exceeded")
                if intent.side == "buy" and asset_class == "options":
                    max_options_notional_pct = _safe_float(constraints.get("max_options_notional_pct"))
                    if max_options_notional_pct > 0 and equity > 0 and (notional / equity) > max_options_notional_pct:
                        blocked.append("options_notional_limit_exceeded")
                if intent.side == "buy" and asset_class == "crypto":
                    max_crypto_notional_pct = _safe_float(constraints.get("max_crypto_notional_pct"))
                    if max_crypto_notional_pct > 0 and equity > 0 and (notional / equity) > max_crypto_notional_pct:
                        blocked.append("crypto_notional_limit_exceeded")
                if intent.side == "buy" and asset_class == "forex":
                    max_forex_notional_pct = _safe_float(constraints.get("max_forex_notional_pct"))
                    if max_forex_notional_pct > 0 and equity > 0 and (notional / equity) > max_forex_notional_pct:
                        blocked.append("forex_notional_limit_exceeded")
                    allowlist = constraints.get("forex_pairs_allowlist")
                    if isinstance(allowlist, list):
                        allowed_pairs = {str(item).strip().upper() for item in allowlist if str(item).strip()}
                        if allowed_pairs and intent.symbol.upper().strip() not in allowed_pairs:
                            blocked.append("forex_pair_not_allowed")
                if intent.side == "buy" and asset_class == "crypto":
                    allowlist = constraints.get("crypto_symbols_allowlist")
                    if isinstance(allowlist, list):
                        allowed_symbols = {str(item).strip().upper() for item in allowlist if str(item).strip()}
                        if allowed_symbols and intent.symbol.upper().strip() not in allowed_symbols:
                            blocked.append("crypto_symbol_not_allowed")
                if intent.side == "buy" and asset_class == "commodities":
                    allowlist = constraints.get("commodity_execution_allowlist")
                    if isinstance(allowlist, list):
                        allowed_symbols = {str(item).strip().upper() for item in allowlist if str(item).strip()}
                        if allowed_symbols and intent.symbol.upper().strip() not in allowed_symbols:
                            blocked.append("commodity_symbol_not_allowed")
                if not bool(constraints.get("weekend_trading_enabled", False)) and _utc_now().weekday() >= 5:
                    blocked.append("weekend_trading_disabled")

            if intent.side == "buy":
                decision_scoring = resolve_decision_scoring(
                    metadata=intent.metadata,
                    symbol=intent.symbol,
                    asset_class=asset_class,
                )
                scoring_metrics = decision_scoring.get("metrics") if isinstance(decision_scoring.get("metrics"), dict) else {}
                strategy_family = str(
                    decision_scoring.get("strategy_family")
                    or intent.metadata.get("strategy_family")
                    or ""
                ).strip().lower()
                portfolio_context = build_portfolio_threshold_context(
                    symbol=intent.symbol,
                    asset_class=asset_class,
                    positions=open_positions,
                    equity=equity,
                    notional=notional,
                    metadata=intent.metadata,
                )
                threshold_profile = resolve_decision_gate_thresholds(
                    self._settings,
                    asset_class=asset_class,
                    strategy_family=strategy_family,
                    portfolio_context=portfolio_context,
                )
                score = _safe_float(decision_scoring.get("score"))
                confidence = _safe_float(decision_scoring.get("confidence"))
                direction = str(decision_scoring.get("direction") or "").strip().lower()
                regime_alignment = _safe_float(scoring_metrics.get("regime_alignment"))
                liquidity_score = _safe_float(scoring_metrics.get("liquidity_score"))
                news_intensity_count = _safe_float(scoring_metrics.get("news_intensity_count"))

                if not decision_scoring:
                    blocked.append("ml_scoring_missing")

                if decision_scoring:
                    if score < threshold_profile.min_score:
                        blocked.append("ml_score_below_threshold")
                    if confidence < threshold_profile.min_confidence:
                        blocked.append("ml_confidence_below_threshold")
                    if regime_alignment < threshold_profile.min_regime_alignment:
                        blocked.append("regime_alignment_below_threshold")
                    if liquidity_score < threshold_profile.min_liquidity_score:
                        blocked.append("liquidity_score_below_threshold")
                    if news_intensity_count > float(threshold_profile.max_news_intensity_count):
                        blocked.append("news_intensity_limit_exceeded")
                    if direction == "short_bias":
                        blocked.append("directional_bias_mismatch")

            if asset_class == "options" and instrument_type != "option_contract":
                blocked.append("invalid_option_contract")
            if asset_class == "forex" and "/" not in intent.symbol:
                blocked.append("invalid_forex_symbol")
            if asset_class == "crypto" and "-" not in intent.symbol:
                blocked.append("invalid_crypto_symbol")
            if asset_class == "options" and routing_mode != "paper_options":
                blocked.append("options_execution_route_invalid")
            if asset_class == "forex" and routing_mode != "paper_forex":
                blocked.append("forex_execution_route_invalid")
            if asset_class == "crypto" and routing_mode != "paper_crypto":
                blocked.append("crypto_execution_route_invalid")
            if asset_class in {"options", "forex", "crypto"} and routing_mode == "paper_equity":
                blocked.append("unsupported_execution_route")

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
