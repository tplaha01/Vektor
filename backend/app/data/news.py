from __future__ import annotations

from datetime import datetime, timedelta

import requests

from app.config import get_settings
from app.fund.runtime_guard import data_integrity_guard

settings = get_settings()
FINNHUB_KEY = settings.FINNHUB_KEY

_cache: dict[str, dict] = {}


def latest_news(symbol: str, limit: int = 8):
    """
    Pull recent company news from Finnhub.
    Returns dicts with source/url/published_at fields.
    """
    now = datetime.utcnow()
    normalized_symbol = str(symbol).upper().strip()
    strict_mode = data_integrity_guard.strict_mode_enabled()

    if normalized_symbol in _cache and (now - _cache[normalized_symbol]["ts"]).seconds < 3600:
        source = str(_cache[normalized_symbol].get("source") or "cache")
        mode = "provider" if source == "finnhub" else "fallback"
        data_integrity_guard.record_provider_event(
            provider="finnhub_news",
            mode=mode,  # type: ignore[arg-type]
            symbol=normalized_symbol,
            detail=f"cache_source:{source}",
        )
        if strict_mode and mode != "provider":
            raise RuntimeError(f"real_data_required:finnhub_cache_untrusted:{normalized_symbol}")
        return _cache[normalized_symbol]["data"]

    if not FINNHUB_KEY:
        data_integrity_guard.record_provider_event(
            provider="finnhub_news",
            mode="fallback",
            symbol=normalized_symbol,
            detail="missing_finnhub_key",
        )
        if strict_mode:
            raise RuntimeError("real_data_required:finnhub_key_missing")
        return _cache.get(normalized_symbol, {}).get("data", _sample_news(normalized_symbol))

    try:
        url = (
            f"https://finnhub.io/api/v1/company-news?"
            f"symbol={normalized_symbol}"
            f"&from={(now - timedelta(days=2)).date()}"
            f"&to={now.date()}"
            f"&token={FINNHUB_KEY}"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("empty_finnhub_response")

        parsed = [
            {
                "symbol": normalized_symbol,
                "headline": item.get("headline", ""),
                "source": item.get("source", "Finnhub"),
                "url": item.get("url", ""),
                "published_at": datetime.utcfromtimestamp(
                    item.get("datetime", now.timestamp())
                ).isoformat(),
            }
            for item in data[:limit]
            if item.get("headline")
        ]

        _cache[normalized_symbol] = {"ts": now, "data": parsed, "source": "finnhub"}
        data_integrity_guard.record_provider_event(
            provider="finnhub_news",
            mode="provider",
            symbol=normalized_symbol,
            detail=f"headline_count:{len(parsed)}",
        )
        return parsed

    except Exception as exc:
        print(f"Finnhub news fetch failed for {normalized_symbol}: {exc}")
        data_integrity_guard.record_provider_event(
            provider="finnhub_news",
            mode="failed",
            symbol=normalized_symbol,
            detail=f"finnhub_error:{exc}",
        )
        if strict_mode:
            raise RuntimeError(f"real_data_required:finnhub_fetch_failed:{normalized_symbol}") from exc
        return _cache.get(normalized_symbol, {}).get("data", _sample_news(normalized_symbol))


def _sample_news(symbol: str):
    now = datetime.utcnow().isoformat()
    examples = [
        ("Company beats earnings expectations, raises guidance for next quarter", "Reuters"),
        ("Regulatory headwinds grow after new antitrust probe is announced", "Bloomberg"),
        ("Strong product launch drives record pre-orders, analysts turn bullish", "CNBC"),
        ("Supply chain disruptions expected to impact margins in near term", "WSJ"),
    ]
    return [
        {
            "symbol": str(symbol).upper(),
            "headline": headline,
            "source": source,
            "url": "",
            "published_at": now,
        }
        for headline, source in examples
    ]

