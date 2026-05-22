from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from app.ml.features import build_features
from app.storage.db import get_db


@dataclass(frozen=True)
class TrainingDataset:
    rows: list[dict[str, Any]]
    source: str
    symbols: list[str]
    forward_days: int
    benchmark_symbol: str | None


def _normalize_bar_rows(rows: Iterable[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        symbol = str(row.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        grouped[symbol].append(
            {
                "ts": str(row.get("ts") or row.get("date") or ""),
                "open": float(row.get("open") or 0.0),
                "high": float(row.get("high") or 0.0),
                "low": float(row.get("low") or 0.0),
                "close": float(row.get("close") or 0.0),
                "volume": float(row.get("volume") or 0.0),
            }
        )

    frames: dict[str, pd.DataFrame] = {}
    for symbol, items in grouped.items():
        frame = pd.DataFrame(items)
        if frame.empty:
            continue
        frame = frame.dropna(subset=["ts", "close"]).sort_values("ts").drop_duplicates(subset=["ts"], keep="last")
        frame = frame.reset_index(drop=True)
        if not frame.empty:
            frames[symbol] = frame
    return frames


def _benchmark_forward_returns(frame: pd.DataFrame, forward_days: int) -> dict[str, float]:
    out: dict[str, float] = {}
    closes = frame["close"].astype(float)
    for idx in range(0, len(frame) - forward_days):
        current = float(closes.iloc[idx])
        future = float(closes.iloc[idx + forward_days])
        if current > 0:
            out[str(frame["ts"].iloc[idx])] = (future - current) / current
    return out


def load_warehouse_training_dataset(
    *,
    symbols: list[str] | None = None,
    timeframe: str = "1d",
    forward_days: int = 5,
    lookback_rows: int = 60,
    min_symbol_rows: int = 100,
    min_quality_score: float = 0.75,
    min_excess_return: float = 0.001,
    transaction_cost_bps: float = 5.0,
    benchmark_symbol: str | None = "SPY",
) -> TrainingDataset:
    """Build supervised alpha rows from persisted warehouse bars.

    Labels are benchmark-adjusted forward returns, net of a simple transaction
    cost haircut. This keeps model training tied to the app's own ingested data
    and avoids training on a different provider surface than execution uses.
    """
    requested = [s.upper().strip() for s in symbols or [] if s and s.strip()]
    params: list[Any] = [timeframe, float(min_quality_score)]
    query = """
        SELECT symbol, ts, open, high, low, close, volume
        FROM data_market_bars
        WHERE timeframe = ? AND quality_score >= ?
    """
    if requested:
        placeholders = ", ".join("?" for _ in requested)
        query += f" AND symbol IN ({placeholders})"
        params.extend(requested)
    query += " ORDER BY symbol ASC, ts ASC"

    with get_db() as db:
        rows = db.execute(query, params).fetchall()

    frames = _normalize_bar_rows(dict(row) for row in rows)
    benchmark_returns: dict[str, float] = {}
    bmk = benchmark_symbol.upper().strip() if benchmark_symbol else None
    if bmk and bmk in frames:
        benchmark_returns = _benchmark_forward_returns(frames[bmk], forward_days)

    cost = float(transaction_cost_bps) / 10_000.0
    out: list[dict[str, Any]] = []

    for symbol, frame in frames.items():
        if len(frame) < max(min_symbol_rows, lookback_rows + forward_days + 1):
            continue
        closes = frame["close"].astype(float)
        for idx in range(lookback_rows - 1, len(frame) - forward_days):
            window = frame.iloc[: idx + 1].copy()
            feat = build_features(window)
            if not feat:
                continue
            current = float(closes.iloc[idx])
            future = float(closes.iloc[idx + forward_days])
            if current <= 0:
                continue
            fwd_return = (future - current) / current
            as_of = str(frame["ts"].iloc[idx])
            benchmark_return = 0.0 if symbol == bmk else benchmark_returns.get(as_of, 0.0)
            excess_return = fwd_return - benchmark_return - cost

            feat["_label"] = int(excess_return > min_excess_return)
            feat["_symbol"] = symbol
            feat["_as_of"] = as_of
            feat["_forward_return"] = float(fwd_return)
            feat["_benchmark_return"] = float(benchmark_return)
            feat["_excess_return"] = float(excess_return)
            out.append(feat)

    out.sort(key=lambda row: str(row.get("_as_of") or ""))
    return TrainingDataset(
        rows=out,
        source="warehouse_bars",
        symbols=sorted([s for s in frames.keys() if s != bmk]),
        forward_days=forward_days,
        benchmark_symbol=bmk,
    )
