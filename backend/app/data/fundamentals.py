from __future__ import annotations

import requests

from app.config import get_settings
from app.fund.runtime_guard import data_integrity_guard

settings = get_settings()
FMP_KEY = settings.FMP_KEY


def _fallback_defaults() -> dict:
    return {
        "revenue_growth": 0.1,
        "gross_margin": 0.4,
        "oper_margin": 0.25,
        "debt_to_equity": 1.0,
        "pe": 25.0,
    }


def get_fundamentals(symbol: str):
    """Fetch basic fundamental ratios from FMP free endpoints."""
    normalized_symbol = str(symbol).upper().strip()

    if not FMP_KEY:
        data_integrity_guard.record_provider_event(
            provider="fmp_fundamentals",
            mode="fallback",
            symbol=normalized_symbol,
            detail="missing_fmp_key",
        )
        if data_integrity_guard.strict_mode_enabled():
            raise RuntimeError("real_data_required:fmp_key_missing")
        return _fallback_defaults()

    try:
        ratios_url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{normalized_symbol}?apikey={FMP_KEY}"
        ratios = requests.get(ratios_url, timeout=10).json()
        r = ratios[0] if isinstance(ratios, list) and ratios else {}

        prof_url = f"https://financialmodelingprep.com/api/v3/profile/{normalized_symbol}?apikey={FMP_KEY}"
        prof = requests.get(prof_url, timeout=10).json()
        p = prof[0] if isinstance(prof, list) and prof else {}

        payload = {
            "revenue_growth": float(r.get("revenueGrowthTTM", 0.05)),
            "gross_margin": float(r.get("grossProfitMarginTTM", 0.35)),
            "oper_margin": float(r.get("operatingProfitMarginTTM", 0.2)),
            "debt_to_equity": float(r.get("debtEquityRatioTTM", 1.0)),
            "pe": float(p.get("pe", 20.0)),
        }
        data_integrity_guard.record_provider_event(
            provider="fmp_fundamentals",
            mode="provider",
            symbol=normalized_symbol,
            detail="ratios_ttm_profile",
        )
        return payload

    except Exception as exc:
        print(f"FMP fetch exception for {normalized_symbol}: {exc}")
        data_integrity_guard.record_provider_event(
            provider="fmp_fundamentals",
            mode="failed",
            symbol=normalized_symbol,
            detail=f"fmp_error:{exc}",
        )
        if data_integrity_guard.strict_mode_enabled():
            raise RuntimeError(f"real_data_required:fmp_fetch_failed:{normalized_symbol}") from exc
        return {
            "revenue_growth": 0.05,
            "gross_margin": 0.35,
            "oper_margin": 0.2,
            "debt_to_equity": 1.0,
            "pe": 20.0,
        }

