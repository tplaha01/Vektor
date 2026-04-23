from types import SimpleNamespace

from app.fund.execution_adapter import ExecutionIntent
from app.fund.policy_gate import PolicyGate, PolicyLimits, resolve_decision_gate_thresholds


def _base_intent(**overrides):
    payload = {
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 10.0,
        "approved": True,
        "decision_id": "decision-1",
        "risk_id": "risk-1",
        "run_id": "run-1",
        "agent_id": "trader-1",
        "broker_mode": "paper",
        "price": 100.0,
        "metadata": {"available_cash": 100_000.0, "sleeve": "tactical"},
    }
    payload.update(overrides)
    return ExecutionIntent(**payload)


def test_policy_gate_allows_valid_intent():
    gate = PolicyGate()
    approved, reasons = gate.evaluate(_base_intent(), positions=[], equity=100_000.0)
    assert approved is True
    assert reasons == []


def test_policy_gate_blocks_live_trading_and_large_notional():
    gate = PolicyGate(limits=PolicyLimits(max_order_notional_usd=25_000.0))
    approved, reasons = gate.evaluate(
        _base_intent(broker_mode="live", quantity=500.0, price=100.0),
        positions=[],
        equity=100_000.0,
    )
    assert approved is False
    assert "live_trading_disabled" in reasons
    assert "order_notional_limit_exceeded" in reasons


def test_policy_gate_blocks_when_available_cash_is_zero():
    gate = PolicyGate()
    approved, reasons = gate.evaluate(
        _base_intent(metadata={"available_cash": 0.0, "sleeve": "tactical"}),
        positions=[],
        equity=100_000.0,
    )
    assert approved is False
    assert "insufficient_cash" in reasons


def test_policy_gate_allows_sell_that_reduces_exposure_even_when_notional_is_large():
    gate = PolicyGate()
    approved, reasons = gate.evaluate(
        _base_intent(
            side="sell",
            quantity=50.0,  # $5,000 notional (50% of equity below)
            price=100.0,
            metadata={"available_cash": 0.0, "sleeve": "tactical"},
        ),
        positions=[{"symbol": "AAPL", "qty": 100.0, "market_price": 10.0, "market_value": 1_000.0}],
        equity=10_000.0,
    )
    assert approved is True
    assert "single_position_notional_limit_exceeded" not in reasons


def test_resolve_decision_gate_thresholds_applies_asset_strategy_precedence():
    settings = SimpleNamespace(
        DECISION_GATE_MIN_SCORE=0.58,
        DECISION_GATE_MIN_CONFIDENCE=0.55,
        DECISION_GATE_MIN_REGIME_ALIGNMENT=0.52,
        DECISION_GATE_MIN_LIQUIDITY_SCORE=0.35,
        DECISION_GATE_MAX_NEWS_INTENSITY_COUNT=10,
        DECISION_GATE_ASSET_CLASS_PROFILES='{"crypto":{"min_score":0.63,"min_confidence":0.6}}',
        DECISION_GATE_STRATEGY_FAMILY_PROFILES='{"multi_signal_scout":{"min_score":0.62,"min_regime_alignment":0.56}}',
        DECISION_GATE_ASSET_STRATEGY_PROFILES='{"crypto:multi_signal_scout":{"min_score":0.67,"min_confidence":0.62,"min_liquidity_score":0.55}}',
    )

    profile = resolve_decision_gate_thresholds(
        settings,
        asset_class="crypto",
        strategy_family="multi_signal_scout",
    )

    assert profile.min_score == 0.67
    assert profile.min_confidence == 0.62
    assert profile.min_regime_alignment == 0.56
    assert profile.min_liquidity_score == 0.55
    assert profile.applied_profiles == (
        "default",
        "asset_class:crypto",
        "strategy_family:multi_signal_scout",
        "asset_strategy:crypto:multi_signal_scout",
    )


def test_policy_gate_uses_asset_class_profile_thresholds():
    gate = PolicyGate()
    gate._settings = SimpleNamespace(
        DECISION_GATE_ML_ENABLED=True,
        DECISION_GATE_MIN_SCORE=0.58,
        DECISION_GATE_MIN_CONFIDENCE=0.55,
        DECISION_GATE_MIN_REGIME_ALIGNMENT=0.52,
        DECISION_GATE_MIN_LIQUIDITY_SCORE=0.35,
        DECISION_GATE_MAX_NEWS_INTENSITY_COUNT=10,
        DECISION_GATE_ASSET_CLASS_PROFILES='{"forex":{"min_score":0.56,"min_confidence":0.53,"min_regime_alignment":0.55,"min_liquidity_score":0.45,"max_news_intensity_count":9}}',
        DECISION_GATE_STRATEGY_FAMILY_PROFILES="{}",
        DECISION_GATE_ASSET_STRATEGY_PROFILES="{}",
    )
    approved, reasons = gate.evaluate(
        _base_intent(
            symbol="EUR/USD",
            asset_class="forex",
            routing_mode="paper_forex",
            instrument_type="spot_fx",
            metadata={
                "available_cash": 100_000.0,
                "sleeve": "tactical",
                "asset_class": "forex",
                "routing_mode": "paper_forex",
                "instrument_type": "spot_fx",
                "decision_scoring": {
                    "score": 0.57,
                    "confidence": 0.54,
                    "direction": "long_bias",
                    "strategy_family": "macro",
                    "metrics": {
                        "regime_alignment": 0.56,
                        "liquidity_score": 0.5,
                        "news_intensity_count": 8,
                    },
                },
            },
        ),
        positions=[],
        equity=100_000.0,
    )
    assert approved is True
    assert "ml_score_below_threshold" not in reasons
    assert "ml_confidence_below_threshold" not in reasons


def test_policy_gate_uses_strategy_family_profile_thresholds():
    gate = PolicyGate()
    gate._settings = SimpleNamespace(
        DECISION_GATE_ML_ENABLED=True,
        DECISION_GATE_MIN_SCORE=0.58,
        DECISION_GATE_MIN_CONFIDENCE=0.55,
        DECISION_GATE_MIN_REGIME_ALIGNMENT=0.52,
        DECISION_GATE_MIN_LIQUIDITY_SCORE=0.35,
        DECISION_GATE_MAX_NEWS_INTENSITY_COUNT=10,
        DECISION_GATE_ASSET_CLASS_PROFILES="{}",
        DECISION_GATE_STRATEGY_FAMILY_PROFILES='{"event_driven":{"min_score":0.66,"min_confidence":0.62,"max_news_intensity_count":5}}',
        DECISION_GATE_ASSET_STRATEGY_PROFILES="{}",
    )
    approved, reasons = gate.evaluate(
        _base_intent(
            metadata={
                "available_cash": 100_000.0,
                "sleeve": "tactical",
                "asset_class": "equities",
                "routing_mode": "paper_equity",
                "instrument_type": "equity",
                "decision_scoring": {
                    "score": 0.67,
                    "confidence": 0.6,
                    "direction": "long_bias",
                    "strategy_family": "event_driven",
                    "metrics": {
                        "regime_alignment": 0.6,
                        "liquidity_score": 0.5,
                        "news_intensity_count": 4,
                    },
                },
            },
        ),
        positions=[],
        equity=100_000.0,
    )
    assert approved is False
    assert "ml_confidence_below_threshold" in reasons


def test_resolve_decision_gate_thresholds_applies_portfolio_adjustments():
    settings = SimpleNamespace(
        DECISION_GATE_MIN_SCORE=0.58,
        DECISION_GATE_MIN_CONFIDENCE=0.55,
        DECISION_GATE_MIN_REGIME_ALIGNMENT=0.52,
        DECISION_GATE_MIN_LIQUIDITY_SCORE=0.35,
        DECISION_GATE_MAX_NEWS_INTENSITY_COUNT=10,
        DECISION_GATE_ASSET_CLASS_PROFILES="{}",
        DECISION_GATE_STRATEGY_FAMILY_PROFILES="{}",
        DECISION_GATE_ASSET_STRATEGY_PROFILES="{}",
    )

    profile = resolve_decision_gate_thresholds(
        settings,
        asset_class="equities",
        strategy_family="multi_signal_scout",
        portfolio_context={
            "macro_risk_level": "risk_off",
            "symbol_exposure_ratio": 0.24,
            "correlated_group_exposure_ratio": 0.31,
            "asset_class_usage_ratio": 0.92,
            "cash_reserve_ratio": 0.08,
            "min_cash_reserve_ratio": 0.1,
        },
    )

    assert profile.min_score > 0.58
    assert profile.min_confidence > 0.55
    assert profile.min_regime_alignment > 0.52
    assert profile.min_liquidity_score > 0.35
    assert profile.max_news_intensity_count < 10
    assert "portfolio:macro_risk:risk_off" in profile.adjustment_reasons
    assert "portfolio:symbol_concentration_high" in profile.adjustment_reasons
    assert "portfolio:correlated_group_high" in profile.adjustment_reasons


def test_policy_gate_uses_portfolio_state_to_tighten_thresholds():
    gate = PolicyGate()
    gate._settings = SimpleNamespace(
        DECISION_GATE_ML_ENABLED=True,
        DECISION_GATE_MIN_SCORE=0.58,
        DECISION_GATE_MIN_CONFIDENCE=0.55,
        DECISION_GATE_MIN_REGIME_ALIGNMENT=0.52,
        DECISION_GATE_MIN_LIQUIDITY_SCORE=0.35,
        DECISION_GATE_MAX_NEWS_INTENSITY_COUNT=10,
        DECISION_GATE_ASSET_CLASS_PROFILES="{}",
        DECISION_GATE_STRATEGY_FAMILY_PROFILES="{}",
        DECISION_GATE_ASSET_STRATEGY_PROFILES="{}",
    )
    approved, reasons = gate.evaluate(
        _base_intent(
            quantity=10.0,
            price=100.0,
            metadata={
                "available_cash": 9_000.0,
                "sleeve": "tactical",
                "asset_class": "equities",
                "routing_mode": "paper_equity",
                "instrument_type": "equity",
                "macro_risk_level": "risk_off",
                "allocation_constraints": {"min_cash_reserve_pct": 0.1},
                "decision_scoring": {
                    "score": 0.6,
                    "confidence": 0.58,
                    "direction": "long_bias",
                    "strategy_family": "multi_signal_scout",
                    "metrics": {
                        "regime_alignment": 0.57,
                        "liquidity_score": 0.4,
                        "news_intensity_count": 6,
                    },
                },
            },
        ),
        positions=[
            {"symbol": "AAPL", "qty": 150.0, "market_price": 100.0, "market_value": 15_000.0, "asset_class": "equities"},
            {"symbol": "NVDA", "qty": 120.0, "market_price": 100.0, "market_value": 12_000.0, "asset_class": "equities"},
        ],
        equity=100_000.0,
    )
    assert approved is False
    assert "ml_score_below_threshold" in reasons
