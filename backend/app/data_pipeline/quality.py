from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import QualityResult


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _score_from_flags(flags: list[str]) -> tuple[float, str]:
    score = 1.0
    for flag in flags:
        if flag in {"missing_payload", "invalid_price", "empty_dataset"}:
            score -= 0.45
        elif flag in {"stale_observation", "missing_timestamp", "missing_volume"}:
            score -= 0.25
        else:
            score -= 0.15
    score = max(0.0, min(1.0, score))
    if score < 0.5:
        severity = "critical"
    elif score < 0.75:
        severity = "warn"
    else:
        severity = "ok"
    return score, severity


def validate_price(symbol: str, provider: str, price: float, observed_at: str | None) -> QualityResult:
    flags: list[str] = []
    if price <= 0:
        flags.append("invalid_price")
    observed = _parse_ts(observed_at)
    if observed is None:
        flags.append("missing_timestamp")
    else:
        age_seconds = max(0.0, (_utc_now() - observed.astimezone(timezone.utc)).total_seconds())
        if age_seconds > 900:
            flags.append("stale_observation")
    score, severity = _score_from_flags(flags)
    return QualityResult("market_price", symbol, provider, score, tuple(flags), severity)


def validate_quote(
    symbol: str,
    provider: str,
    bid_price: float,
    ask_price: float,
    observed_at: str | None,
    *,
    max_spread_bps: float = 100.0,
) -> QualityResult:
    flags: list[str] = []
    if bid_price <= 0 or ask_price <= 0:
        flags.append("invalid_quote")
    if bid_price > ask_price:
        flags.append("crossed_market")
    mid = (bid_price + ask_price) / 2.0 if bid_price > 0 and ask_price > 0 else 0.0
    spread_bps = ((ask_price - bid_price) / mid * 10_000.0) if mid > 0 else 0.0
    if spread_bps > max_spread_bps:
        flags.append("wide_spread")
    observed = _parse_ts(observed_at)
    if observed is None:
        flags.append("missing_timestamp")
    else:
        age_seconds = max(0.0, (_utc_now() - observed.astimezone(timezone.utc)).total_seconds())
        if age_seconds > 30:
            flags.append("stale_observation")
    score, severity = _score_from_flags(flags)
    return QualityResult(
        "market_quote",
        symbol,
        provider,
        score,
        tuple(flags),
        severity,
        {"spread_bps": round(spread_bps, 6), "max_spread_bps": max_spread_bps},
    )


def validate_bars(
    symbol: str,
    provider: str,
    rows: list[dict[str, Any]],
    *,
    max_age_days: float = 5.0,
) -> QualityResult:
    flags: list[str] = []
    if not rows:
        flags.append("empty_dataset")
    last_close = 0.0
    newest_ts: datetime | None = None
    for row in rows[-10:]:
        close = float(row.get("close") or 0.0)
        volume = float(row.get("volume") or 0.0)
        ts = row.get("ts")
        parsed_ts = _parse_ts(ts)
        if close <= 0:
            flags.append("invalid_price")
        if volume <= 0:
            flags.append("missing_volume")
        if not parsed_ts:
            flags.append("missing_timestamp")
        elif newest_ts is None or parsed_ts > newest_ts:
            newest_ts = parsed_ts
        if last_close > 0 and close > 0:
            move = abs((close / last_close) - 1.0)
            if move > 0.35:
                flags.append("price_jump")
        last_close = close or last_close
    if newest_ts is not None:
        age_days = max(0.0, (_utc_now() - newest_ts.astimezone(timezone.utc)).total_seconds() / 86400.0)
        if age_days > max_age_days:
            flags.append("stale_observation")
    score, severity = _score_from_flags(sorted(set(flags)))
    metadata = {"latest_bar_ts": newest_ts.isoformat() if newest_ts else None, "max_age_days": max_age_days}
    return QualityResult("market_bars", symbol, provider, score, tuple(sorted(set(flags))), severity, metadata)


def validate_text_event(
    symbol: str | None,
    provider: str,
    title: str,
    published_at: str | None,
    *,
    max_age_hours: float = 72.0,
) -> QualityResult:
    flags: list[str] = []
    if not title.strip():
        flags.append("missing_payload")
    parsed_ts = _parse_ts(published_at)
    if not parsed_ts:
        flags.append("missing_timestamp")
    else:
        age_hours = max(0.0, (_utc_now() - parsed_ts.astimezone(timezone.utc)).total_seconds() / 3600.0)
        if age_hours > max_age_hours:
            flags.append("stale_observation")
    score, severity = _score_from_flags(flags)
    metadata = {"published_at": published_at, "max_age_hours": max_age_hours}
    return QualityResult("text_event", symbol, provider, score, tuple(flags), severity, metadata)


def validate_fundamentals(symbol: str, provider: str, metrics: dict[str, Any]) -> QualityResult:
    flags: list[str] = []
    if not metrics:
        flags.append("empty_dataset")
    for key in ("revenue_growth", "gross_margin", "oper_margin", "debt_to_equity", "pe"):
        if key not in metrics:
            flags.append(f"missing_metric:{key}")
    score, severity = _score_from_flags(flags)
    return QualityResult("fundamentals", symbol, provider, score, tuple(flags), severity)
