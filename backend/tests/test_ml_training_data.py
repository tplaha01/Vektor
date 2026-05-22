from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.data_pipeline.models import QualityResult
from app.data_pipeline.warehouse import warehouse
from app.ml.training_data import load_warehouse_training_dataset
from app.storage import db as storage_db


def _bars(symbol: str, *, base: float, slope: float, rows: int = 130) -> list[dict]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    out = []
    for idx in range(rows):
        close = base + slope * idx
        out.append(
            {
                "ts": (start + timedelta(days=idx)).isoformat().replace("+00:00", "Z"),
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000 + idx * 100,
            }
        )
    return out


def test_warehouse_training_dataset_uses_forward_excess_return_labels(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "training.db"))
    get_settings.cache_clear()
    storage_db._conn = None
    storage_db.init_db()

    quality = QualityResult(dataset="bars", symbol=None, provider="unit", score=1.0)
    warehouse.save_market_bars(
        symbol="SPY",
        asset_class="equities",
        timeframe="1d",
        rows=_bars("SPY", base=400, slope=0.05),
        provider="unit",
        raw_id=None,
        quality=quality,
    )
    warehouse.save_market_bars(
        symbol="AAPL",
        asset_class="equities",
        timeframe="1d",
        rows=_bars("AAPL", base=100, slope=0.4),
        provider="unit",
        raw_id=None,
        quality=quality,
    )

    dataset = load_warehouse_training_dataset(
        symbols=["AAPL", "SPY"],
        forward_days=5,
        lookback_rows=60,
        min_symbol_rows=100,
        transaction_cost_bps=1,
        benchmark_symbol="SPY",
    )

    assert dataset.source == "warehouse_bars"
    assert dataset.forward_days == 5
    assert dataset.benchmark_symbol == "SPY"
    assert len(dataset.rows) > 40
    assert {row["_symbol"] for row in dataset.rows} == {"AAPL", "SPY"}
    assert {"_forward_return", "_benchmark_return", "_excess_return", "_as_of"} <= set(dataset.rows[0])
    assert any(row["_benchmark_return"] == 0.0 for row in dataset.rows if row["_symbol"] == "SPY")
    assert any(row["_label"] == 1 for row in dataset.rows if row["_symbol"] == "AAPL")
