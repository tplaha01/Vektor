from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.core_engine.contracts import DataFreshness, EngineInputSnapshot
from app.core_engine.registry.model_registry import get_active_model_versions
from app.data.fundamentals import get_fundamentals
from app.data.market_data import FEED
from app.data.news import latest_news

_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)
_FUNDAMENTAL_TS_KEYS = (
    "as_of",
    "updated_at",
    "fetched_at",
    "timestamp",
    "report_date",
    "filing_date",
    "date",
)


def _to_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = pd.to_datetime(value, utc=True)
    except Exception:
        return None
    if hasattr(parsed, "to_pydatetime"):
        dt = parsed.to_pydatetime()
    elif isinstance(parsed, datetime):
        dt = parsed
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        pass
    return default


def _normalize_hist(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    cols = {str(c).lower(): c for c in df.columns}
    rename: dict[str, str] = {}
    for src, dst in (
        ("date", "ts"),
        ("datetime", "ts"),
        ("timestamp", "ts"),
        ("ts", "ts"),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
    ):
        if src in cols:
            rename[cols[src]] = dst

    out = df.rename(columns=rename).copy()
    for col in ("ts", "open", "high", "low", "close", "volume"):
        if col not in out.columns:
            out[col] = np.nan
    out = out[["ts", "open", "high", "low", "close", "volume"]]
    for col in ("open", "high", "low", "close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["ts"] = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    out = out.dropna(subset=["ts", "close", "high", "low"]).sort_values("ts").reset_index(drop=True)
    return out


def _normalize_news(news: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[tuple[tuple[int, float, str, str, str], dict[str, Any]]] = []
    for raw in news:
        item = dict(raw or {})
        source = str(item.get("source") or "unknown").strip()
        headline = str(item.get("headline") or "").strip()
        url = str(item.get("url") or "").strip()
        published_dt = _to_utc_datetime(item.get("published_at"))
        if published_dt is not None:
            item["published_at"] = _to_utc_iso(published_dt)
            sort_key = (0, -published_dt.timestamp(), source.lower(), headline.lower(), url)
        else:
            if item.get("published_at") is not None:
                item["published_at"] = str(item.get("published_at"))
            sort_key = (1, 0.0, source.lower(), headline.lower(), url)
        normalized.append((sort_key, item))
    normalized.sort(key=lambda row: row[0])
    return [item for _, item in normalized]


def _extract_fundamentals_timestamp(fundamentals: dict[str, Any]) -> datetime | None:
    for key in _FUNDAMENTAL_TS_KEYS:
        parsed = _to_utc_datetime(fundamentals.get(key))
        if parsed is not None:
            return parsed
    return None


def _resolve_as_of(
    history: pd.DataFrame,
    fundamentals_timestamp: datetime | None,
    news: list[dict[str, Any]],
) -> datetime:
    candidates: list[datetime] = []
    if len(history) > 0:
        hist_ts = _to_utc_datetime(history["ts"].iloc[-1])
        if hist_ts is not None:
            candidates.append(hist_ts)
    if fundamentals_timestamp is not None:
        candidates.append(fundamentals_timestamp)
    for item in news[:24]:
        published = _to_utc_datetime(item.get("published_at"))
        if published is not None:
            candidates.append(published)
    if not candidates:
        return _EPOCH_UTC
    return max(candidates)


def _age_minutes(reference_ts: datetime, observed_ts: datetime | None) -> float | None:
    if observed_ts is None:
        return None
    return max(0.0, (reference_ts - observed_ts).total_seconds() / 60.0)


def _extract_sentiment_age_minutes(news: list[dict[str, Any]], reference_ts: datetime) -> float | None:
    if not news:
        return None
    ages: list[float] = []
    for item in news:
        published = _to_utc_datetime(item.get("published_at"))
        if published is None:
            continue
        ages.append(max(0.0, (reference_ts - published).total_seconds() / 60.0))
    if not ages:
        return None
    return float(min(ages))


def _extract_fundamentals_age_hours(reference_ts: datetime, fundamentals_ts: datetime | None) -> float | None:
    age_minutes = _age_minutes(reference_ts, fundamentals_ts)
    if age_minutes is None:
        return None
    return float(age_minutes / 60.0)


def _hash_payload(payload: dict[str, Any]) -> str:
    packed = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def build_point_in_time_snapshot(symbol: str, profile: str, bars: int = 320, news_limit: int = 24) -> EngineInputSnapshot:
    sym = str(symbol or "").upper().strip()
    history = _normalize_hist(FEED.history(sym, bars=bars))
    fundamentals = dict(get_fundamentals(sym) or {})
    news = _normalize_news(list(latest_news(sym, limit=news_limit) or []))

    model_versions = get_active_model_versions(profile)
    fundamentals_ts = _extract_fundamentals_timestamp(fundamentals)
    as_of_dt = _resolve_as_of(history, fundamentals_ts, news)
    as_of = _to_utc_iso(as_of_dt)

    history_ts = _to_utc_datetime(history["ts"].iloc[-1]) if len(history) > 0 else None
    quality_flags: list[str] = []
    if len(history) < 80:
        quality_flags.append("insufficient_market_history")
    for field in ("revenue_growth", "gross_margin", "oper_margin", "debt_to_equity", "pe"):
        if field not in fundamentals:
            quality_flags.append("fundamentals_incomplete")
            break
    if fundamentals_ts is None:
        quality_flags.append("fundamentals_timestamp_missing")
    if not news:
        quality_flags.append("sentiment_news_missing")
    if any(not str(version).strip() for version in model_versions.values()):
        quality_flags.append("model_versions_incomplete")

    freshness = DataFreshness(
        as_of=as_of,
        market_age_minutes=_age_minutes(as_of_dt, history_ts),
        sentiment_age_minutes=_extract_sentiment_age_minutes(news, as_of_dt),
        fundamentals_age_hours=_extract_fundamentals_age_hours(as_of_dt, fundamentals_ts),
        quality_flags=quality_flags,
    )

    feature_fingerprint = _hash_payload(
        {
            "symbol": sym,
            "as_of": as_of,
            "profile": profile,
            "closes_tail": [round(_safe_float(v), 6) for v in history["close"].tail(32).tolist()] if len(history) else [],
            "fundamentals": {k: round(_safe_float(v), 6) for k, v in sorted(fundamentals.items())},
            "fundamentals_ts": _to_utc_iso(fundamentals_ts) if fundamentals_ts is not None else None,
            "news": [
                {
                    "published_at": str(item.get("published_at") or ""),
                    "source": str(item.get("source") or ""),
                    "headline": str(item.get("headline") or "")[:160],
                }
                for item in news[:12]
            ],
        }
    )
    lineage = {
        "run_id": f"run-{feature_fingerprint[:16]}",
        "decision_id": f"decision-{feature_fingerprint[16:32]}",
        "feature_hash": feature_fingerprint,
    }

    return EngineInputSnapshot(
        symbol=sym,
        as_of=as_of,
        profile=profile,
        history=history,
        fundamentals=fundamentals,
        news=news,
        freshness=freshness,
        lineage=lineage,
        model_versions=model_versions,
    )
