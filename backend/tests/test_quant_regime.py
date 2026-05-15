from __future__ import annotations

import pandas as pd

from app.quant.regime import infer_market_regime, infer_portfolio_risk_regime, technical_score


def _trend_frame(direction: float = 1.0) -> pd.DataFrame:
    closes = [100 + direction * i for i in range(80)]
    highs = [c + 1.5 for c in closes]
    lows = [c - 1.5 for c in closes]
    vols = [1_000_000 + (i * 1_000) for i in range(80)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": vols,
        }
    )


def test_market_regime_detects_trend_up():
    snapshot = infer_market_regime(_trend_frame(1.0))
    assert snapshot.regime in {"TREND_UP", "BREAKOUT_UP", "RANGE"}
    assert snapshot.direction in {"long_bias", "neutral"}
    assert snapshot.confidence >= 0.0
    assert isinstance(technical_score(_trend_frame(1.0)), float)


def test_market_regime_detects_trend_down():
    snapshot = infer_market_regime(_trend_frame(-1.0))
    assert snapshot.direction in {"short_bias", "neutral"}
    assert snapshot.confidence >= 0.0


def test_portfolio_risk_regime_flags_concentration():
    positions = [
        {"symbol": "NVDA", "asset_class": "equities", "qty": 10, "market_price": 100.0, "market_value": 1000.0},
        {"symbol": "AAPL", "asset_class": "equities", "qty": 10, "market_price": 100.0, "market_value": 1000.0},
    ]
    snapshot = infer_portfolio_risk_regime(
        symbol="NVDA",
        asset_class="equities",
        positions=positions,
        equity=10_000.0,
        notional=2_000.0,
        metadata={
            "available_cash": 1_000.0,
            "allocation_constraints": {"min_cash_reserve_pct": 0.15},
            "asset_class_budget_allocated_usd": 5_000.0,
            "asset_class_budget_used_usd": 4_600.0,
        },
    )
    assert snapshot.macro_risk_level in {"volatile", "stressed", "risk_off"}
    assert snapshot.risk_score >= 0.0
