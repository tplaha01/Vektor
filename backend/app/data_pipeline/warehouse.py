from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from app.storage.db import get_db

from .models import FeatureVector, QualityResult


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_id(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


class QuantDataWarehouse:
    def __init__(self) -> None:
        self._lock = RLock()

    def save_raw_event(
        self,
        *,
        provider: str,
        endpoint: str,
        asset_class: str,
        symbol: str | None,
        request: dict[str, Any],
        payload: Any,
        provider_ts: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        ingested_at = utc_iso()
        payload_json = json_dumps(payload)
        checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        raw_id = stable_id(provider, endpoint, symbol or "", checksum, ingested_at)
        with self._lock, get_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO data_raw_events
                (raw_id, provider, endpoint, asset_class, symbol, request_json, payload_json,
                 payload_checksum, provider_ts, ingested_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_id,
                    provider,
                    endpoint,
                    asset_class,
                    symbol,
                    json_dumps(request),
                    payload_json,
                    checksum,
                    provider_ts,
                    ingested_at,
                    json_dumps(metadata or {}),
                ),
            )
        return raw_id

    def save_quality(self, result: QualityResult) -> str:
        checked_at = utc_iso()
        quality_id = stable_id(result.dataset, result.symbol or "", result.provider, result.score, result.flags, checked_at)
        with self._lock, get_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO data_quality_events
                (quality_id, dataset, symbol, provider, score, flags_json, severity, checked_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quality_id,
                    result.dataset,
                    result.symbol,
                    result.provider,
                    float(result.score),
                    json_dumps(list(result.flags)),
                    result.severity,
                    checked_at,
                    json_dumps(result.metadata),
                ),
            )
        return quality_id

    def save_market_price(
        self,
        *,
        symbol: str,
        asset_class: str,
        price: float,
        provider: str,
        source_mode: str,
        observed_at: str,
        raw_id: str | None,
        quality: QualityResult,
    ) -> None:
        with self._lock, get_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO data_market_prices
                (symbol, asset_class, price, provider, source_mode, observed_at, ingested_at,
                 raw_id, quality_score, quality_flags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    asset_class,
                    float(price),
                    provider,
                    source_mode,
                    observed_at,
                    utc_iso(),
                    raw_id,
                    float(quality.score),
                    json_dumps(list(quality.flags)),
                ),
            )

    def save_market_quote(
        self,
        *,
        symbol: str,
        asset_class: str,
        bid_price: float,
        bid_size: float | None,
        ask_price: float,
        ask_size: float | None,
        provider: str,
        source_mode: str,
        observed_at: str,
        raw_id: str | None,
        quality: QualityResult,
    ) -> None:
        mid_price = ((float(bid_price) + float(ask_price)) / 2.0) if bid_price > 0 and ask_price > 0 else 0.0
        spread = max(0.0, float(ask_price) - float(bid_price))
        spread_bps = (spread / mid_price * 10_000.0) if mid_price > 0 else 0.0
        with self._lock, get_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO data_market_quotes
                (symbol, asset_class, bid_price, bid_size, ask_price, ask_size, mid_price,
                 spread, spread_bps, provider, source_mode, observed_at, ingested_at,
                 raw_id, quality_score, quality_flags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    asset_class,
                    float(bid_price),
                    bid_size,
                    float(ask_price),
                    ask_size,
                    mid_price,
                    spread,
                    spread_bps,
                    provider,
                    source_mode,
                    observed_at,
                    utc_iso(),
                    raw_id,
                    float(quality.score),
                    json_dumps(list(quality.flags)),
                ),
            )

    def save_market_bars(
        self,
        *,
        symbol: str,
        asset_class: str,
        timeframe: str,
        rows: list[dict[str, Any]],
        provider: str,
        raw_id: str | None,
        quality: QualityResult,
        adjusted: bool = False,
    ) -> int:
        inserted = 0
        with self._lock, get_db() as db:
            for row in rows:
                ts = str(row.get("ts") or "").strip()
                if not ts:
                    continue
                db.execute(
                    """
                    INSERT OR REPLACE INTO data_market_bars
                    (symbol, asset_class, timeframe, ts, open, high, low, close, volume,
                     provider, raw_id, adjusted, quality_score, quality_flags_json, ingested_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        asset_class,
                        timeframe,
                        ts,
                        float(row.get("open") or 0.0),
                        float(row.get("high") or 0.0),
                        float(row.get("low") or 0.0),
                        float(row.get("close") or 0.0),
                        float(row.get("volume") or 0.0),
                        provider,
                        raw_id,
                        1 if adjusted else 0,
                        float(quality.score),
                        json_dumps(list(quality.flags)),
                        utc_iso(),
                    ),
                )
                inserted += 1
        return inserted

    def save_text_events(self, rows: list[dict[str, Any]]) -> int:
        inserted = 0
        with self._lock, get_db() as db:
            for row in rows:
                db.execute(
                    """
                    INSERT OR REPLACE INTO data_text_events
                    (event_id, symbol, asset_class, source_type, provider, title, body, url,
                     published_at, ingested_at, raw_id, sentiment_score, quality_score,
                     quality_flags_json, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["event_id"],
                        row.get("symbol"),
                        row.get("asset_class", "equities"),
                        row.get("source_type", "news"),
                        row.get("provider", "unknown"),
                        row.get("title", ""),
                        row.get("body"),
                        row.get("url"),
                        row.get("published_at"),
                        row.get("ingested_at") or utc_iso(),
                        row.get("raw_id"),
                        row.get("sentiment_score"),
                        float(row.get("quality_score") or 0.0),
                        json_dumps(row.get("quality_flags") or []),
                        json_dumps(row.get("metadata") or {}),
                    ),
                )
                inserted += 1
        return inserted

    def save_fundamentals(
        self,
        *,
        symbol: str,
        asset_class: str,
        provider: str,
        metric_date: str,
        period: str,
        metrics: dict[str, Any],
        raw_id: str | None,
        quality: QualityResult,
    ) -> None:
        with self._lock, get_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO data_fundamentals
                (symbol, asset_class, provider, metric_date, period, metrics_json, raw_id,
                 quality_score, quality_flags_json, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    asset_class,
                    provider,
                    metric_date,
                    period,
                    json_dumps(metrics),
                    raw_id,
                    float(quality.score),
                    json_dumps(list(quality.flags)),
                    utc_iso(),
                ),
            )

    def load_recent_bars(self, symbol: str, timeframe: str = "1d", limit: int = 260) -> list[dict[str, Any]]:
        with self._lock, get_db() as db:
            rows = db.execute(
                """
                SELECT * FROM data_market_bars
                WHERE symbol = ? AND timeframe = ?
                ORDER BY ts DESC
                LIMIT ?
                """,
                (symbol.upper(), timeframe, int(limit)),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def save_feature_vector(self, vector: FeatureVector) -> str:
        created_at = utc_iso()
        feature_id = stable_id(vector.symbol, vector.use_case, vector.as_of, vector.source_snapshot_id)
        with self._lock, get_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO data_feature_vectors
                (feature_id, symbol, asset_class, use_case, as_of, features_json, score,
                 category, source_snapshot_id, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feature_id,
                    vector.symbol,
                    vector.asset_class,
                    vector.use_case,
                    vector.as_of,
                    json_dumps(vector.features),
                    float(vector.score),
                    vector.category,
                    vector.source_snapshot_id,
                    json_dumps(vector.metadata),
                    created_at,
                ),
            )
        return feature_id

    def latest_features(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, get_db() as db:
            rows = db.execute(
                """
                SELECT * FROM data_feature_vectors
                WHERE symbol = ?
                ORDER BY as_of DESC
                LIMIT ?
                """,
                (symbol.upper(), int(limit)),
            ).fetchall()
        items = []
        for row in rows:
            payload = dict(row)
            payload["features"] = json.loads(payload.pop("features_json") or "{}")
            payload["metadata"] = json.loads(payload.pop("metadata_json") or "{}")
            items.append(payload)
        return items

    def save_run(self, run: dict[str, Any]) -> None:
        with self._lock, get_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO data_pipeline_runs
                (run_id, run_type, status, started_at, finished_at, symbols_json,
                 counts_json, quality_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run["run_id"],
                    run["run_type"],
                    run["status"],
                    run["started_at"],
                    run.get("finished_at"),
                    json_dumps(run.get("symbols") or []),
                    json_dumps(run.get("counts") or {}),
                    json_dumps(run.get("quality") or {}),
                    json_dumps(run.get("metadata") or {}),
                ),
            )

    def status(self) -> dict[str, Any]:
        with self._lock, get_db() as db:
            counts = {}
            for table in (
                "data_raw_events",
                "data_market_prices",
                "data_market_quotes",
                "data_market_bars",
                "data_text_events",
                "data_fundamentals",
                "data_quality_events",
                "data_feature_vectors",
                "data_pipeline_runs",
                "data_provider_health",
                "data_snapshots",
            ):
                row = db.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
                counts[table] = int(row["count"] if row else 0)
            latest_run = db.execute(
                "SELECT * FROM data_pipeline_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return {
            "counts": counts,
            "latest_run": dict(latest_run) if latest_run else None,
        }

    def upsert_provider_health(
        self,
        *,
        provider: str,
        status: str,
        success: bool,
        stale: bool = False,
        error: str | None = None,
        event_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = utc_iso()
        provider_key = provider.strip().lower()
        with self._lock, get_db() as db:
            current = db.execute(
                "SELECT * FROM data_provider_health WHERE provider = ?",
                (provider_key,),
            ).fetchone()
            success_count = int(current["success_count"] if current else 0) + (1 if success else 0)
            failure_count = int(current["failure_count"] if current else 0) + (0 if success else 1)
            stale_count = int(current["stale_count"] if current else 0) + (1 if stale else 0)
            db.execute(
                """
                INSERT OR REPLACE INTO data_provider_health
                (provider, status, last_event_at, last_success_at, last_failure_at,
                 success_count, failure_count, stale_count, last_error, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_key,
                    status,
                    event_at or now,
                    (event_at or now) if success else (current["last_success_at"] if current else None),
                    (event_at or now) if not success else (current["last_failure_at"] if current else None),
                    success_count,
                    failure_count,
                    stale_count,
                    error,
                    json_dumps(metadata or {}),
                    now,
                ),
            )

    def provider_health(self) -> list[dict[str, Any]]:
        with self._lock, get_db() as db:
            rows = db.execute(
                "SELECT * FROM data_provider_health ORDER BY updated_at DESC"
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["metadata"] = json.loads(payload.pop("metadata_json") or "{}")
            items.append(payload)
        return items

    def save_snapshot(
        self,
        *,
        snapshot_type: str,
        symbol: str | None,
        as_of: str,
        source_ids: list[str],
        payload: dict[str, Any],
        quality: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        snapshot_id = stable_id(snapshot_type, symbol or "", as_of, source_ids)
        with self._lock, get_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO data_snapshots
                (snapshot_id, snapshot_type, symbol, as_of, source_ids_json, payload_json,
                 quality_json, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    snapshot_type,
                    symbol,
                    as_of,
                    json_dumps(source_ids),
                    json_dumps(payload),
                    json_dumps(quality),
                    json_dumps(metadata or {}),
                    utc_iso(),
                ),
            )
        return snapshot_id

    def load_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self._lock, get_db() as db:
            row = db.execute(
                "SELECT * FROM data_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["source_ids"] = json.loads(payload.pop("source_ids_json") or "[]")
        payload["payload"] = json.loads(payload.pop("payload_json") or "{}")
        payload["quality"] = json.loads(payload.pop("quality_json") or "{}")
        payload["metadata"] = json.loads(payload.pop("metadata_json") or "{}")
        return payload

    def latest_rows(self, table: str, limit: int = 50) -> list[dict[str, Any]]:
        allowed = {
            "data_raw_events": "ingested_at",
            "data_market_prices": "observed_at",
            "data_market_quotes": "observed_at",
            "data_market_bars": "ts",
            "data_text_events": "published_at",
            "data_fundamentals": "ingested_at",
            "data_quality_events": "checked_at",
            "data_feature_vectors": "created_at",
            "data_pipeline_runs": "started_at",
            "data_snapshots": "created_at",
            "data_provider_health": "updated_at",
        }
        if table not in allowed:
            raise ValueError(f"unsupported_table:{table}")
        order_col = allowed[table]
        with self._lock, get_db() as db:
            rows = db.execute(
                f"SELECT * FROM {table} ORDER BY {order_col} DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]


warehouse = QuantDataWarehouse()
