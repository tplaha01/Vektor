from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests
from zoneinfo import ZoneInfo

from app.config import Settings


_EASTERN = ZoneInfo("America/New_York")


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _in_test_mode() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("VEKTOR_TEST_MODE") == "1"


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": str(settings.ALPACA_API_KEY or ""),
        "APCA-API-SECRET-KEY": str(settings.ALPACA_SECRET_KEY or ""),
    }


def _fallback_weekday_status(reason: str, source: str) -> dict[str, Any]:
    now_et = datetime.now(_EASTERN)
    trading_day = now_et.weekday() < 5
    # Weekday fallback cannot determine market open session windows precisely without a provider clock.
    market_open = bool(trading_day)
    return {
        "open": market_open,
        "trading_day": trading_day,
        "reason": "market_open" if market_open else "weekend_or_holiday",
        "source": source,
        "checked_at": _utc_iso_now(),
        "error": reason,
    }


def market_session_status(settings: Settings) -> dict[str, Any]:
    """
    Resolve current tradability status for US equities.

    Priority:
    1) Alpaca clock+calendar (when credentials exist) for holiday/weekend/session fidelity.
    2) Local weekday fallback.
    """
    if _in_test_mode():
        return {
            "open": True,
            "trading_day": True,
            "reason": "test_mode",
            "source": "test_mode",
            "checked_at": _utc_iso_now(),
        }

    if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
        return _fallback_weekday_status("missing_alpaca_credentials", "local_weekday_fallback")

    base = str(settings.ALPACA_BASE_URL or "https://paper-api.alpaca.markets").rstrip("/")
    headers = _headers(settings)

    try:
        timeout = 3.0
        clock_resp = requests.get(f"{base}/v2/clock", headers=headers, timeout=timeout)
        clock_resp.raise_for_status()
        clock_data = clock_resp.json() if isinstance(clock_resp.json(), dict) else {}
        is_open = bool(clock_data.get("is_open"))
        next_open = clock_data.get("next_open")
        next_close = clock_data.get("next_close")

        today_et = datetime.now(_EASTERN).date().isoformat()
        cal_resp = requests.get(
            f"{base}/v2/calendar",
            headers=headers,
            params={"start": today_et, "end": today_et},
            timeout=timeout,
        )
        cal_resp.raise_for_status()
        cal_rows = cal_resp.json() if isinstance(cal_resp.json(), list) else []
        trading_day = bool(cal_rows)

        if is_open:
            reason = "market_open"
        elif not trading_day:
            reason = "weekend_or_holiday"
        else:
            reason = "market_closed_session"

        return {
            "open": is_open,
            "trading_day": trading_day,
            "reason": reason,
            "source": "alpaca_clock",
            "checked_at": _utc_iso_now(),
            "next_open": next_open,
            "next_close": next_close,
        }
    except Exception as exc:
        return _fallback_weekday_status(str(exc), "local_weekday_fallback")

