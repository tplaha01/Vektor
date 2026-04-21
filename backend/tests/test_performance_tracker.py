import asyncio

from app.fund import performance_tracker as tracker_module


class _BrokerStub:
    def __init__(self):
        self.cash = 100_000.0
        self.positions = {
            "NVDA": {
                "symbol": "NVDA",
                "qty": 10.0,
                "avg_price": 100.0,
            }
        }
        self.order_history = [
            {
                "symbol": "NVDA",
                "side": "buy",
                "qty": 10,
                "avg_price": 100.0,
                "created_at": "2026-04-20T13:00:00Z",
            }
        ]

    def list_positions(self, price_lookup):
        price = float(price_lookup("NVDA"))
        return [
            {
                "symbol": "NVDA",
                "qty": 10.0,
                "avg_price": 100.0,
                "market_price": price,
                "market_value": 10.0 * price,
                "unrealized_pnl": 10.0 * (price - 100.0),
            }
        ]

    def get_cash(self):
        return self.cash

    def get_portfolio_value(self, price_lookup):
        return self.cash + (10.0 * float(price_lookup("NVDA")))


class _Settings:
    PERFORMANCE_TRACKER_ENABLED = True
    PERFORMANCE_TRACKER_INTERVAL_SECONDS = 900
    PERFORMANCE_TRACKER_BENCHMARKS = "SPY,QQQ"
    BROKER = "paper"


def test_performance_tracker_capture_and_summary(monkeypatch):
    baseline_store = {}
    snapshot_store = []
    knowledge_events = []

    monkeypatch.setattr(tracker_module, "broker", _BrokerStub())
    monkeypatch.setattr(tracker_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        tracker_module.knowledge_graph,
        "ingest",
        lambda **kwargs: knowledge_events.append(dict(kwargs)),
    )
    monkeypatch.setattr(
        tracker_module.storage_db,
        "save_benchmark_baseline",
        lambda symbol, baseline_price, baseline_at, metadata=None: baseline_store.setdefault(
            symbol,
            {
                "symbol": symbol,
                "baseline_price": baseline_price,
                "baseline_at": baseline_at,
                "metadata": dict(metadata or {}),
            },
        ),
    )
    monkeypatch.setattr(
        tracker_module.storage_db,
        "load_benchmark_baselines",
        lambda: dict(baseline_store),
    )
    monkeypatch.setattr(
        tracker_module.storage_db,
        "save_performance_snapshot",
        lambda snapshot: snapshot_store.append(dict(snapshot)),
    )
    monkeypatch.setattr(
        tracker_module.storage_db,
        "load_performance_snapshots",
        lambda limit=None, snapshot_kind=None, start_at=None, end_at=None: [
            row
            for row in snapshot_store
            if snapshot_kind is None or row.get("snapshot_kind") == snapshot_kind
        ][-limit if limit is not None and limit >= 0 else 0 :] if snapshot_store else [],
    )
    monkeypatch.setattr(
        tracker_module.storage_db,
        "load_latest_performance_snapshot",
        lambda snapshot_kind=None: next(
            (
                row
                for row in reversed(snapshot_store)
                if snapshot_kind is None or row.get("snapshot_kind") == snapshot_kind
            ),
            None,
        ),
    )
    monkeypatch.setattr(
        tracker_module.storage_db,
        "count_performance_snapshots",
        lambda snapshot_kind=None: len(
            [
                row
                for row in snapshot_store
                if snapshot_kind is None or row.get("snapshot_kind") == snapshot_kind
            ]
        ),
    )

    prices = {"NVDA": 120.0, "SPY": 500.0, "QQQ": 400.0}
    tracker = tracker_module.PerformanceTracker(price_lookup=lambda symbol: prices[symbol])

    asyncio.run(tracker.capture_snapshot(snapshot_kind="daily", reason="day_1"))
    prices["NVDA"] = 130.0
    prices["SPY"] = 510.0
    prices["QQQ"] = 420.0
    asyncio.run(tracker.capture_snapshot(snapshot_kind="daily", reason="day_2"))

    assert len(snapshot_store) == 2
    assert set(baseline_store.keys()) == {"SPY", "QQQ"}
    assert len(knowledge_events) == 2

    summary = tracker.summary()
    assert summary["snapshot_count"] == 2
    assert summary["daily_snapshot_count"] == 2
    assert summary["track_record"]["sample_days"] == 2
    assert summary["track_record"]["total_return_pct"] > 0
    assert summary["track_record"]["alpha_vs_primary_benchmark_pct"] != 0
