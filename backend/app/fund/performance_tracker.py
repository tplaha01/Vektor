from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from statistics import pstdev
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.analytics import build_metrics_from_broker
from app.config import get_settings
from app.core.context import broker
from app.data.market_data import FEED
from app.fund.knowledge_graph import knowledge_graph
from app.storage import db as storage_db


_EASTERN = ZoneInfo("America/New_York")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime | None = None) -> str:
    dt = value or _utc_now()
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str | None) -> datetime:
    if not value:
        return _utc_now()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return _utc_now()


def _safe_price(price_lookup: Callable[[str], float], symbol: str) -> float:
    try:
        value = float(price_lookup(symbol))
        if math.isfinite(value) and value > 0:
            return value
    except Exception:
        pass
    return 0.0


def _make_snapshot_id(kind: str, recorded_at: str) -> str:
    stamp = recorded_at.replace(":", "").replace("-", "").replace(".", "")
    return f"perf-{kind}-{stamp}"


class PerformanceTracker:
    def __init__(
        self,
        *,
        price_lookup: Callable[[str], float] | None = None,
    ) -> None:
        self._price_lookup = price_lookup or FEED.price
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_snapshot_at: datetime | None = None
        self._last_daily_key: str | None = None
        self._baseline_cache: dict[str, dict[str, Any]] = {}

    def _settings(self):
        return get_settings()

    def restore_from_storage(self) -> dict[str, Any]:
        self._baseline_cache = storage_db.load_benchmark_baselines()
        latest = storage_db.load_latest_performance_snapshot()
        latest_daily = storage_db.load_latest_performance_snapshot(snapshot_kind="daily")
        self._last_snapshot_at = _parse_ts(latest.get("recorded_at")) if latest else None
        self._last_daily_key = None
        if latest_daily:
            daily_ts = _parse_ts(latest_daily.get("recorded_at"))
            self._last_daily_key = daily_ts.astimezone(_EASTERN).date().isoformat()
        return {
            "restored": True,
            "baseline_count": len(self._baseline_cache),
            "snapshot_count": storage_db.count_performance_snapshots(),
            "last_snapshot_at": latest.get("recorded_at") if latest else None,
            "last_daily_at": latest_daily.get("recorded_at") if latest_daily else None,
        }

    async def start(self) -> None:
        settings = self._settings()
        if not settings.PERFORMANCE_TRACKER_ENABLED or self._running:
            return
        self._running = True
        await self.capture_snapshot(snapshot_kind="startup", reason="backend_startup")
        self._task = asyncio.create_task(self._run_loop(), name="performance-tracker-loop")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        settings = self._settings()
        interval = max(60, int(settings.PERFORMANCE_TRACKER_INTERVAL_SECONDS or 900))
        while self._running:
            try:
                await self.capture_if_due()
            except Exception:
                # Deliberately non-fatal: performance capture should not take down runtime.
                pass
            await asyncio.sleep(interval)

    async def capture_if_due(self) -> dict[str, Any] | None:
        settings = self._settings()
        now = _utc_now()
        interval = max(60, int(settings.PERFORMANCE_TRACKER_INTERVAL_SECONDS or 900))
        should_intraday = (
            self._last_snapshot_at is None
            or (now - self._last_snapshot_at).total_seconds() >= interval
        )
        latest = None
        if should_intraday:
            latest = await self.capture_snapshot(snapshot_kind="intraday", reason="scheduled_interval")

        daily_key = now.astimezone(_EASTERN).date().isoformat()
        if self._last_daily_key != daily_key:
            latest = await self.capture_snapshot(snapshot_kind="daily", reason="new_trading_day_rollover")
            self._last_daily_key = daily_key
        return latest

    async def capture_snapshot(self, *, snapshot_kind: str = "manual", reason: str = "manual") -> dict[str, Any]:
        recorded_at = _utc_iso()
        metrics = build_metrics_from_broker(broker)
        positions = broker.list_positions(self._price_lookup)
        cash = float(broker.get_cash())
        market_value = sum(float(row.get("market_value") or 0.0) for row in positions)
        unrealized = sum(float(row.get("unrealized_pnl") or 0.0) for row in positions)
        realized = float(metrics.get("realized_pnl") or 0.0)
        equity = float(broker.get_portfolio_value(self._price_lookup))
        total_pnl = realized + unrealized
        benchmarks = self._resolve_benchmarks(recorded_at)
        row = {
            "snapshot_id": _make_snapshot_id(snapshot_kind, recorded_at),
            "snapshot_kind": snapshot_kind,
            "recorded_at": recorded_at,
            "broker_mode": str(self._settings().BROKER or "paper"),
            "equity": equity,
            "cash": cash,
            "market_value": market_value,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": total_pnl,
            "total_trades": int(metrics.get("total_trades") or 0),
            "closed_trades": int(metrics.get("closed_trades") or 0),
            "wins": int(metrics.get("wins") or 0),
            "losses": int(metrics.get("losses") or 0),
            "win_rate": float(metrics.get("win_rate") or 0.0),
            "max_drawdown": float(metrics.get("max_drawdown") or 0.0),
            "positions": positions,
            "benchmarks": benchmarks,
            "metadata": {
                "reason": reason,
                "recent_trades": list(metrics.get("recent_trades") or []),
            },
        }
        storage_db.save_performance_snapshot(row)
        self._last_snapshot_at = _parse_ts(recorded_at)
        knowledge_graph.ingest(
            source="performance_tracker",
            event_type="performance.snapshot.stored",
            occurred_at=recorded_at,
            payload={
                "snapshot_id": row["snapshot_id"],
                "snapshot_kind": snapshot_kind,
                "equity": equity,
                "cash": cash,
                "total_pnl": total_pnl,
                "reason": reason,
            },
        )
        return row

    def list_snapshots(
        self,
        *,
        limit: int = 500,
        snapshot_kind: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> list[dict[str, Any]]:
        return storage_db.load_performance_snapshots(
            limit=limit,
            snapshot_kind=snapshot_kind,
            start_at=start_at,
            end_at=end_at,
        )

    def summary(self) -> dict[str, Any]:
        snapshots = storage_db.load_performance_snapshots(limit=-1)
        daily = storage_db.load_performance_snapshots(limit=-1, snapshot_kind="daily")
        latest = snapshots[-1] if snapshots else None
        first = daily[0] if daily else (snapshots[0] if snapshots else None)
        primary_benchmark = None
        if latest:
            benchmarks = list(latest.get("benchmarks") or [])
            if benchmarks:
                primary_benchmark = benchmarks[0]
        equity_curve = [float(row.get("equity") or 0.0) for row in daily or snapshots]
        max_drawdown_pct = self._max_drawdown_pct(equity_curve)
        sharpe = self._sharpe_ratio(daily or snapshots)

        total_return_pct = 0.0
        benchmark_return_pct = 0.0
        alpha_pct = 0.0
        if latest and first:
            first_equity = float(first.get("equity") or 0.0)
            latest_equity = float(latest.get("equity") or 0.0)
            if first_equity > 0:
                total_return_pct = ((latest_equity / first_equity) - 1.0) * 100.0
            if primary_benchmark:
                benchmark_return_pct = float(primary_benchmark.get("return_pct") or 0.0)
                alpha_pct = total_return_pct - benchmark_return_pct

        return {
            "enabled": bool(self._settings().PERFORMANCE_TRACKER_ENABLED),
            "snapshot_count": len(snapshots),
            "daily_snapshot_count": len(daily),
            "latest_snapshot": latest,
            "inception_snapshot": first,
            "track_record": {
                "total_return_pct": round(total_return_pct, 4),
                "max_drawdown_pct": round(max_drawdown_pct, 4),
                "sharpe_ratio": None if sharpe is None else round(sharpe, 4),
                "alpha_vs_primary_benchmark_pct": round(alpha_pct, 4),
                "primary_benchmark_return_pct": round(benchmark_return_pct, 4),
                "sample_days": len(daily),
            },
            "baselines": self._baseline_cache,
        }

    def reset(self) -> dict[str, int]:
        self._baseline_cache = {}
        self._last_snapshot_at = None
        self._last_daily_key = None
        return storage_db.clear_performance_history()

    def _resolve_benchmarks(self, recorded_at: str) -> list[dict[str, Any]]:
        symbols = [
            part.strip().upper()
            for part in str(self._settings().PERFORMANCE_TRACKER_BENCHMARKS or "").split(",")
            if part.strip()
        ]
        benchmarks: list[dict[str, Any]] = []
        for symbol in symbols:
            price = _safe_price(self._price_lookup, symbol)
            if price <= 0:
                continue
            baseline = self._baseline_cache.get(symbol)
            if not baseline:
                baseline = {
                    "symbol": symbol,
                    "baseline_price": price,
                    "baseline_at": recorded_at,
                    "metadata": {"source": "performance_tracker"},
                }
                storage_db.save_benchmark_baseline(
                    symbol=symbol,
                    baseline_price=price,
                    baseline_at=recorded_at,
                    metadata=baseline["metadata"],
                )
                self._baseline_cache[symbol] = baseline
            baseline_price = float(baseline.get("baseline_price") or 0.0)
            return_pct = ((price / baseline_price) - 1.0) * 100.0 if baseline_price > 0 else 0.0
            benchmarks.append(
                {
                    "symbol": symbol,
                    "price": round(price, 6),
                    "baseline_price": round(baseline_price, 6),
                    "baseline_at": baseline.get("baseline_at"),
                    "return_pct": round(return_pct, 4),
                }
            )
        return benchmarks

    @staticmethod
    def _max_drawdown_pct(equity_curve: list[float]) -> float:
        peak = 0.0
        worst = 0.0
        for value in equity_curve:
            if value > peak:
                peak = value
            if peak > 0:
                drawdown_pct = ((value / peak) - 1.0) * 100.0
                if drawdown_pct < worst:
                    worst = drawdown_pct
        return worst

    @staticmethod
    def _sharpe_ratio(snapshots: list[dict[str, Any]]) -> float | None:
        if len(snapshots) < 3:
            return None
        returns: list[float] = []
        prev_equity: float | None = None
        for row in snapshots:
            equity = float(row.get("equity") or 0.0)
            if prev_equity and prev_equity > 0:
                returns.append((equity / prev_equity) - 1.0)
            prev_equity = equity
        if len(returns) < 2:
            return None
        mean = sum(returns) / len(returns)
        vol = pstdev(returns)
        if vol <= 1e-12:
            return None
        return (mean / vol) * math.sqrt(252.0)


performance_tracker = PerformanceTracker()
