from __future__ import annotations

from datetime import datetime, timezone

from app.analytics import build_metrics_from_broker


class _BrokerStub:
    def __init__(self, order_history):
        self.order_history = order_history


def test_build_metrics_handles_mixed_naive_and_aware_timestamps():
    broker = _BrokerStub(
        [
            {
                "symbol": "AAPL",
                "side": "buy",
                "qty": 1,
                "avg_price": 100.0,
                "created_at": datetime(2026, 1, 1, 10, 0, 0),  # naive
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "qty": 1,
                "avg_price": 105.0,
                "created_at": datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc),  # aware
            },
        ]
    )

    metrics = build_metrics_from_broker(broker)

    assert metrics["total_trades"] == 1
    assert metrics["realized_pnl"] == 5.0
    assert len(metrics["recent_trades"]) == 1

