from __future__ import annotations

import numpy as np
import pandas as pd


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else default
    except Exception:
        return default


def clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return float(np.clip(float(value), low, high))


def trend_sign(value: float, threshold: float = 0.0) -> float:
    if value > threshold:
        return 1.0
    if value < -threshold:
        return -1.0
    return 0.0


def price_group(symbol: str, asset_class: str, metadata: dict[str, object] | None = None) -> str:
    meta = metadata if isinstance(metadata, dict) else {}
    explicit = str(meta.get("correlation_group") or "").strip().lower()
    if explicit:
        return explicit

    normalized_symbol = str(symbol or "").upper().strip()
    normalized_asset_class = str(asset_class or "").strip().lower()
    if normalized_asset_class == "forex":
        return "fx_usd"
    if normalized_asset_class == "crypto":
        return "crypto_beta"
    if normalized_asset_class == "commodities":
        return "commodity_macro"
    if normalized_symbol in {"SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMD", "AMZN", "GOOGL", "META", "TSLA", "XLK"}:
        return "equity_growth"
    if normalized_symbol in {"XLF", "JPM", "BAC", "GS"}:
        return "equity_financials"
    if normalized_symbol in {"XLE", "USO", "UNG", "GLD", "SLV"}:
        return "commodity_macro"
    if normalized_symbol in {"TLT", "IEF", "SHY"}:
        return "rates_duration"
    return f"{normalized_asset_class or 'unknown'}_general"


def close_high_low_volume(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)
    return close, high, low, volume


_safe_float = safe_float
_clip = clip
_trend_sign = trend_sign
_price_group = price_group
_series_close_high_low_volume = close_high_low_volume
