from __future__ import annotations

import numpy as np

from app.quant.common import price_group, safe_float
from app.quant.types import PortfolioRegimeSnapshot


def infer_portfolio_risk_regime(
    *,
    symbol: str,
    asset_class: str,
    positions: list[dict[str, object]],
    equity: float,
    notional: float,
    metadata: dict[str, object] | None = None,
) -> PortfolioRegimeSnapshot:
    meta = metadata if isinstance(metadata, dict) else {}
    constraints = meta.get("allocation_constraints") if isinstance(meta.get("allocation_constraints"), dict) else {}
    normalized_symbol = str(symbol or "").upper().strip()
    normalized_asset_class = str(asset_class or "").strip().lower()
    correlation_group = price_group(normalized_symbol, normalized_asset_class, meta)

    symbol_exposure = 0.0
    correlated_group_exposure = 0.0
    gross_exposure = 0.0
    for position in positions:
        position_symbol = str(position.get("symbol") or "").upper().strip()
        position_asset_class = str(position.get("asset_class") or normalized_asset_class or "equities").strip().lower()
        position_meta = position.get("metadata") if isinstance(position.get("metadata"), dict) else {}
        position_market_value = safe_float(position.get("market_value"))
        if position_market_value <= 0:
            position_market_value = max(0.0, safe_float(position.get("qty")) * safe_float(position.get("market_price")))
        gross_exposure += max(0.0, position_market_value)
        if position_symbol == normalized_symbol:
            symbol_exposure += position_market_value
        if price_group(position_symbol, position_asset_class, position_meta) == correlation_group:
            correlated_group_exposure += position_market_value

    available_cash = safe_float(meta.get("available_cash"))
    min_cash_reserve_pct = safe_float(constraints.get("min_cash_reserve_pct"))
    asset_allocated = safe_float(meta.get("asset_class_budget_allocated_usd"))
    asset_used = safe_float(meta.get("asset_class_budget_used_usd"))
    projected_symbol_exposure = symbol_exposure + max(0.0, notional)
    projected_group_exposure = correlated_group_exposure + max(0.0, notional)
    projected_asset_usage = asset_used + max(0.0, notional)
    projected_cash = available_cash - max(0.0, notional)
    cash_reserve_ratio = (projected_cash / equity) if equity > 0 else 0.0
    symbol_ratio = (projected_symbol_exposure / equity) if equity > 0 else 0.0
    group_ratio = (projected_group_exposure / equity) if equity > 0 else 0.0
    asset_usage_ratio = (projected_asset_usage / asset_allocated) if asset_allocated > 0 else 0.0
    leverage_ratio = (gross_exposure / equity) if equity > 0 else 0.0

    risk_score = float(
        np.clip(
            (
                0.30 * np.clip(symbol_ratio / 0.25, 0.0, 1.0)
                + 0.25 * np.clip(group_ratio / 0.30, 0.0, 1.0)
                + 0.20 * np.clip(asset_usage_ratio / 0.90, 0.0, 1.0)
                + 0.15 * np.clip((min_cash_reserve_pct - cash_reserve_ratio) / 0.05, 0.0, 1.0)
                + 0.10 * np.clip((leverage_ratio - 1.0) / 0.5, 0.0, 1.0)
            ),
            0.0,
            1.0,
        )
    )

    notes: list[str] = []
    if cash_reserve_ratio < min_cash_reserve_pct:
        notes.append("cash_reserve_breach")
    if symbol_ratio >= 0.22:
        notes.append("symbol_concentration_high")
    elif symbol_ratio >= 0.15:
        notes.append("symbol_concentration_elevated")
    if group_ratio >= 0.30:
        notes.append("correlated_group_high")
    elif group_ratio >= 0.22:
        notes.append("correlated_group_elevated")
    if asset_usage_ratio >= 0.90:
        notes.append("asset_budget_near_full")
    elif asset_usage_ratio >= 0.75:
        notes.append("asset_budget_tight")
    if leverage_ratio >= 1.20:
        notes.append("portfolio_leverage_high")

    if risk_score >= 0.75:
        macro_risk_level = "risk_off"
    elif risk_score >= 0.55:
        macro_risk_level = "stressed"
    elif risk_score >= 0.35 or meta.get("event_risk_active", False):
        macro_risk_level = "volatile"
    else:
        macro_risk_level = "normal"

    return PortfolioRegimeSnapshot(
        macro_risk_level=macro_risk_level,
        risk_score=risk_score,
        symbol_exposure_ratio=symbol_ratio,
        correlated_group_exposure_ratio=group_ratio,
        asset_class_usage_ratio=asset_usage_ratio,
        cash_reserve_ratio=cash_reserve_ratio,
        leverage_ratio=leverage_ratio,
        notes=tuple(notes),
        metrics={
            "gross_exposure": gross_exposure,
            "projected_symbol_exposure": projected_symbol_exposure,
            "projected_group_exposure": projected_group_exposure,
            "projected_asset_usage": projected_asset_usage,
            "cash_reserve_ratio": cash_reserve_ratio,
            "min_cash_reserve_ratio": min_cash_reserve_pct,
            "available_cash": available_cash,
        },
    )
