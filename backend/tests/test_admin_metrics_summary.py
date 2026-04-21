from app import admin_research_routes as admin_routes
from app.risk.engine import RiskEngine


def test_metrics_summary_uses_performance_tracker(monkeypatch):
    monkeypatch.setattr(
        admin_routes.performance_tracker,
        "summary",
        lambda: {
            "latest_snapshot": {
                "equity": 125000.0,
                "realized_pnl": 12000.0,
                "unrealized_pnl": 3000.0,
                "positions": [{"symbol": "NVDA"}, {"symbol": "MSFT"}],
                "win_rate": 62.5,
            },
            "inception_snapshot": {
                "equity": 100000.0,
                "recorded_at": "2026-04-20T00:00:00Z",
            },
            "track_record": {
                "total_return_pct": 25.0,
                "max_drawdown_pct": 4.75,
                "sharpe_ratio": 1.82,
            },
        },
    )
    monkeypatch.setattr(admin_routes.broker, "get_portfolio_value", lambda _: 125000.0)
    monkeypatch.setattr(
        admin_routes.risk,
        "status",
        lambda: {
            "drawdown_breaker": {
                "current_drawdown": 0.013,
                "max_drawdown_threshold": 0.10,
            }
        },
    )

    summary = admin_routes._metrics_summary_from_performance()

    assert summary is not None
    assert summary.total_equity == 125000.0
    assert summary.equity_change == 25.0
    assert summary.baseline_equity == 100000.0
    assert summary.active_positions == 2
    assert summary.sharpe_ratio == 1.82


def test_risk_engine_reset_clears_breakers_and_stops():
    engine = RiskEngine()
    engine._equity = 150000.0
    engine.dd_breaker._halted = True
    engine.dd_breaker._halt_equity = 120000.0
    engine.stop_manager.register("NVDA", 100.0, 4.0, "long")

    status = engine.reset(starting_equity=100000.0)

    assert status["equity"] == 100000.0
    assert status["drawdown_breaker"]["halted"] is False
    assert status["open_stops"] == []
