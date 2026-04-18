from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


class _BrokerStub:
    def list_positions(self, _price_lookup):
        return [
            {
                "symbol": "SPY",
                "qty": 100,
                "avg_price": 500.0,
                "market_price": 600.0997,
                "market_value": 60009.97,
                "unrealized_pnl": 10009.97,
            }
        ]


class _RiskStub:
    INITIAL_EQUITY = 100_000.0

    def update_equity(self, _positions, _realized):
        return 206_117.11

    def status(self):
        return {
            "drawdown_breaker": {
                "current_drawdown": 0.01,
                "max_drawdown_threshold": 0.10,
            }
        }


def test_metrics_summary_uses_strategy_adjusted_equity_when_capital_flows_exist(monkeypatch):
    monkeypatch.setattr(admin_routes, "broker", _BrokerStub())
    monkeypatch.setattr(admin_routes, "risk", _RiskStub())
    monkeypatch.setattr(
        admin_routes,
        "build_metrics_from_broker",
        lambda _broker: {
            "realized_pnl": -3560.95,
            "max_drawdown": -3600.0,
            "win_rate": 48.5,
            "recent_trades": [],  # sharpe should be 0 for low sample
        },
    )

    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app)

    response = client.get("/api/admin/metrics/summary")
    assert response.status_code == 200
    payload = response.json()

    # Account equity includes historical external capital injections.
    assert payload["account_equity"] == 206117.11
    # Dashboard equity is strategy-adjusted against baseline capital.
    assert payload["total_equity"] == 106449.02
    assert payload["equity_change"] == 6.45
    assert payload["external_capital_flow_usd"] == 99668.09
    assert payload["sharpe_ratio"] == 0.0


def test_sharpe_from_recent_trades_is_guarded_and_clamped():
    trades = []
    for i in range(20):
        pnl = 30.0 if i % 2 == 0 else -1.0
        trades.append({"qty": 1.0, "buy": 100.0, "pnl": pnl})

    value = admin_routes._estimate_sharpe_from_recent_trades({"recent_trades": trades})
    assert isinstance(value, float)
    assert -10.0 <= value <= 10.0
