from __future__ import annotations

import re
from typing import Any


ASSET_CLASSES: tuple[str, ...] = ("equities", "options", "commodities", "forex", "crypto", "cash")

DEFAULT_ASSET_WEIGHTS: dict[str, float] = {
    "equities": 0.55,
    "options": 0.10,
    "commodities": 0.10,
    "forex": 0.10,
    "crypto": 0.05,
    "cash": 0.10,
}

DEFAULT_SLEEVE_WEIGHTS: dict[str, float] = {
    "long_term": 0.50,
    "recurring": 0.30,
    "tactical": 0.20,
}

DEFAULT_CONSTRAINTS: dict[str, Any] = {
    "allow_unallocated_capital": False,
    "cash_hold_enabled": True,
    "min_cash_reserve_pct": 0.10,
    "max_single_trade_notional_pct": 0.20,
    "max_asset_class_exposure_pct": 0.60,
    "max_options_notional_pct": 0.05,
    "max_crypto_notional_pct": 0.05,
    "max_forex_notional_pct": 0.10,
    "weekend_trading_enabled": False,
    "holiday_trading_enabled": False,
    "allowed_asset_classes": ["equities", "options", "commodities", "forex", "crypto"],
    "forex_pairs_allowlist": ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CAD", "AUD/USD", "NZD/USD", "USD/CHF"],
    "crypto_symbols_allowlist": ["BTC-USD", "ETH-USD", "SOL-USD"],
    "commodity_execution_allowlist": ["GLD", "SLV", "USO", "UNG", "DBA"],
}


def normalize_asset_class(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "equity": "equities",
        "stock": "equities",
        "stocks": "equities",
        "option": "options",
        "futures": "commodities",
        "future": "commodities",
        "fx": "forex",
        "currencies": "forex",
        "currency": "forex",
        "digital_assets": "crypto",
        "digital_asset": "crypto",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in ASSET_CLASSES:
        return normalized
    return "equities"


def infer_asset_class(symbol: str | None, explicit: str | None = None) -> str:
    if explicit:
        return normalize_asset_class(explicit)
    text = str(symbol or "").strip().upper()
    if not text:
        return "equities"
    if re.fullmatch(r"[A-Z]{1,6}\d{6}[CP]\d{8}", text):
        return "options"
    if "/" in text and len(text.replace("/", "")) >= 6:
        return "forex"
    if text.endswith("USD") and "-" in text:
        return "crypto"
    if any(text.startswith(prefix) for prefix in ("BTC", "ETH", "SOL", "XRP", "DOGE")):
        return "crypto"
    if text in {"GLD", "SLV", "USO", "UNG", "DBA"}:
        return "commodities"
    if text in {"TLT", "IEF", "SHY"}:
        return "equities"
    return "equities"


def infer_instrument_type(symbol: str | None, asset_class: str | None = None) -> str:
    normalized_asset_class = normalize_asset_class(asset_class) if asset_class else infer_asset_class(symbol)
    text = str(symbol or "").strip().upper()
    if normalized_asset_class == "options":
        return "option_contract"
    if normalized_asset_class == "forex":
        return "fx_spot"
    if normalized_asset_class == "crypto":
        return "crypto_spot"
    if normalized_asset_class == "commodities":
        return "commodity_etf" if text in {"GLD", "SLV", "USO", "UNG", "DBA"} else "commodity_future"
    return "equity"


def infer_underlier_symbol(symbol: str | None, asset_class: str | None = None) -> str | None:
    text = str(symbol or "").strip().upper()
    normalized_asset_class = normalize_asset_class(asset_class) if asset_class else infer_asset_class(symbol)
    if normalized_asset_class == "options" and re.fullmatch(r"([A-Z]{1,6})\d{6}[CP]\d{8}", text):
        return re.fullmatch(r"([A-Z]{1,6})\d{6}[CP]\d{8}", text).group(1)
    if normalized_asset_class in {"equities", "commodities"}:
        return text or None
    if normalized_asset_class == "crypto":
        return text.split("-", 1)[0] if "-" in text else text or None
    if normalized_asset_class == "forex":
        return text.replace("/", "")[:6] or None
    return text or None


def infer_routing_mode(symbol: str | None, asset_class: str | None = None) -> str:
    normalized_asset_class = normalize_asset_class(asset_class) if asset_class else infer_asset_class(symbol)
    instrument_type = infer_instrument_type(symbol, normalized_asset_class)
    if normalized_asset_class == "equities":
        return "paper_equity"
    if normalized_asset_class == "commodities" and instrument_type == "commodity_etf":
        return "paper_equity_proxy"
    if normalized_asset_class == "options":
        return "paper_options"
    if normalized_asset_class == "commodities":
        return "paper_commodities_pending_adapter"
    if normalized_asset_class == "forex":
        return "paper_forex"
    if normalized_asset_class == "crypto":
        return "paper_crypto"
    return "paper_equity"


def _normalized_weights(source: dict[str, Any] | None, defaults: dict[str, float]) -> dict[str, float]:
    raw = dict(defaults)
    for key, value in dict(source or {}).items():
        clean_key = str(key or "").strip().lower()
        if clean_key not in raw:
            continue
        try:
            raw[clean_key] = max(0.0, float(value))
        except Exception:
            continue
    total = sum(raw.values())
    if total <= 0:
        return dict(defaults)
    return {key: (value / total) for key, value in raw.items()}


def build_default_policy(
    *,
    total_capital_usd: float,
    reserve_cash_usd: float,
    run_id: str | None = None,
    asset_weights: dict[str, Any] | None = None,
    sleeve_weights: dict[str, Any] | None = None,
    constraints: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deployable = max(0.0, float(total_capital_usd) - float(reserve_cash_usd))
    merged_constraints = dict(DEFAULT_CONSTRAINTS)
    merged_constraints.update(dict(constraints or {}))
    asset_mix = _normalized_weights(asset_weights, DEFAULT_ASSET_WEIGHTS)
    sleeve_mix = _normalized_weights(sleeve_weights, DEFAULT_SLEEVE_WEIGHTS)
    asset_budgets = {
        asset_class: round(deployable * weight, 2)
        for asset_class, weight in asset_mix.items()
    }
    sleeve_budgets = {
        sleeve: round(deployable * weight, 2)
        for sleeve, weight in sleeve_mix.items()
    }
    return {
        "run_id": run_id,
        "status": "active",
        "total_capital_usd": round(float(total_capital_usd), 2),
        "reserve_cash_usd": round(float(reserve_cash_usd), 2),
        "deployable_capital_usd": round(deployable, 2),
        "asset_weights": asset_mix,
        "sleeve_weights": sleeve_mix,
        "asset_budgets": asset_budgets,
        "sleeve_budgets": sleeve_budgets,
        "constraints": merged_constraints,
        "metadata": dict(metadata or {}),
    }
