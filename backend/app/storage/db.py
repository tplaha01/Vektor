from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List

from .schema_sql import SCHEMA_SQL
from ..config import get_settings

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        raise RuntimeError("Database not initialized - call init_db() at startup")
    return _conn


def init_db() -> None:
    """Called once at FastAPI startup. Creates the SQLite file + schema."""
    global _conn
    settings = get_settings()
    _conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.executescript(SCHEMA_SQL)
    _ensure_column(_conn, "orders", "asset_class", "TEXT")
    _ensure_column(_conn, "orders", "instrument_type", "TEXT")
    _ensure_column(_conn, "orders", "routing_mode", "TEXT")
    _ensure_column(_conn, "orders", "underlier_symbol", "TEXT")
    _ensure_column(_conn, "orders", "contract_multiplier", "REAL")
    _ensure_column(_conn, "orders", "metadata_json", "TEXT")
    _ensure_column(_conn, "positions", "asset_class", "TEXT")
    _ensure_column(_conn, "positions", "instrument_type", "TEXT")
    _ensure_column(_conn, "positions", "routing_mode", "TEXT")
    _ensure_column(_conn, "positions", "underlier_symbol", "TEXT")
    _ensure_column(_conn, "positions", "contract_multiplier", "REAL")
    _ensure_column(_conn, "positions", "metadata_json", "TEXT")
    _conn.commit()
    print(f"Database initialized at {settings.SQLITE_PATH}")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_sql: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {str(row[1]) for row in rows}
    if column in names:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_sql}")


@contextmanager
def get_db():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# Orders
def save_order(order: Dict[str, Any]) -> None:
    with get_db() as db:
        db.execute(
            """INSERT OR REPLACE INTO orders
               (id, symbol, side, qty, avg_price, status, created_at, asset_class, instrument_type, routing_mode, underlier_symbol, contract_multiplier, metadata_json)
               VALUES (:id, :symbol, :side, :qty, :avg_price, :status, :created_at, :asset_class, :instrument_type, :routing_mode, :underlier_symbol, :contract_multiplier, :metadata_json)""",
            {
                "id": str(order["id"]),
                "symbol": order["symbol"],
                "side": order["side"],
                "qty": float(order["qty"]),
                "avg_price": float(order.get("avg_price", order.get("price", 0))),
                "status": order.get("status", "filled"),
                "created_at": order.get("created_at", datetime.utcnow().isoformat()),
                "asset_class": order.get("asset_class"),
                "instrument_type": order.get("instrument_type"),
                "routing_mode": order.get("routing_mode"),
                "underlier_symbol": order.get("underlier_symbol"),
                "contract_multiplier": float(order.get("contract_multiplier", 1.0) or 1.0),
                "metadata_json": json.dumps(dict(order.get("metadata") or {}), ensure_ascii=False),
            },
        )


def load_orders() -> List[Dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM orders ORDER BY created_at").fetchall()
        items = []
        for row in rows:
            payload = dict(row)
            try:
                payload["metadata"] = json.loads(payload.get("metadata_json") or "{}")
            except Exception:
                payload["metadata"] = {}
            payload.pop("metadata_json", None)
            items.append(payload)
        return items


# Positions
def save_positions(positions: Dict[str, Dict]) -> None:
    """Replaces entire positions table with current in-memory state."""
    with get_db() as db:
        db.execute("DELETE FROM positions")
        for sym, pos in positions.items():
            db.execute(
                """
                INSERT INTO positions
                (symbol, qty, avg_price, asset_class, instrument_type, routing_mode, underlier_symbol, contract_multiplier, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sym,
                    float(pos["qty"]),
                    float(pos["avg_price"]),
                    pos.get("asset_class"),
                    pos.get("instrument_type"),
                    pos.get("routing_mode"),
                    pos.get("underlier_symbol"),
                    float(pos.get("contract_multiplier", 1.0) or 1.0),
                    json.dumps(dict(pos.get("metadata") or {}), ensure_ascii=False),
                ),
            )


def load_positions() -> Dict[str, Dict]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM positions").fetchall()
        results: Dict[str, Dict] = {}
        for row in rows:
            payload = dict(row)
            try:
                metadata = json.loads(payload.get("metadata_json") or "{}")
            except Exception:
                metadata = {}
            results[row["symbol"]] = {
                "symbol": row["symbol"],
                "qty": row["qty"],
                "avg_price": row["avg_price"],
                "asset_class": payload.get("asset_class") or "equities",
                "instrument_type": payload.get("instrument_type") or "equity",
                "routing_mode": payload.get("routing_mode") or "paper_equity",
                "underlier_symbol": payload.get("underlier_symbol"),
                "contract_multiplier": float(payload.get("contract_multiplier") or 1.0),
                "metadata": metadata,
            }
        return results


# Cash
def save_cash(cash: float) -> None:
    with get_db() as db:
        db.execute(
            "INSERT INTO cash_snapshots (cash, recorded_at) VALUES (?, ?)",
            (cash, datetime.utcnow().isoformat()),
        )


def load_latest_cash(default: float = 100_000.0) -> float:
    with get_db() as db:
        row = db.execute(
            "SELECT cash FROM cash_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["cash"] if row else default


def clear_paper_broker_state(starting_cash: float = 100_000.0) -> Dict[str, Any]:
    target_cash = float(starting_cash)
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        orders_row = db.execute("SELECT COUNT(*) AS c FROM orders").fetchone()
        positions_row = db.execute("SELECT COUNT(*) AS c FROM positions").fetchone()
        cash_row = db.execute("SELECT COUNT(*) AS c FROM cash_snapshots").fetchone()
        deleted_orders = int(orders_row["c"] if orders_row else 0)
        deleted_positions = int(positions_row["c"] if positions_row else 0)
        deleted_cash_snapshots = int(cash_row["c"] if cash_row else 0)

        db.execute("DELETE FROM orders")
        db.execute("DELETE FROM positions")
        db.execute("DELETE FROM cash_snapshots")
        db.execute(
            "INSERT INTO cash_snapshots (cash, recorded_at) VALUES (?, ?)",
            (target_cash, now),
        )

    return {
        "deleted_orders": deleted_orders,
        "deleted_positions": deleted_positions,
        "deleted_cash_snapshots": deleted_cash_snapshots,
        "starting_cash": target_cash,
        "recorded_at": now,
    }


# Blog posts
def save_blog_post(post: Dict[str, Any]) -> None:
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        db.execute(
            """
            INSERT INTO blog_posts (
                id, source_report_id, source_run_id, slug, title, excerpt, category,
                author, author_role, content, tags_json, views, read_time_minutes,
                status, metadata_json, created_at, published_at, updated_at
            ) VALUES (
                :id, :source_report_id, :source_run_id, :slug, :title, :excerpt, :category,
                :author, :author_role, :content, :tags_json, :views, :read_time_minutes,
                :status, :metadata_json, :created_at, :published_at, :updated_at
            )
            ON CONFLICT(id) DO UPDATE SET
                source_report_id=excluded.source_report_id,
                source_run_id=excluded.source_run_id,
                slug=excluded.slug,
                title=excluded.title,
                excerpt=excluded.excerpt,
                category=excluded.category,
                author=excluded.author,
                author_role=excluded.author_role,
                content=excluded.content,
                tags_json=excluded.tags_json,
                views=excluded.views,
                read_time_minutes=excluded.read_time_minutes,
                status=excluded.status,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            {
                "id": str(post["id"]),
                "source_report_id": post.get("source_report_id"),
                "source_run_id": post.get("source_run_id"),
                "slug": str(post["slug"]),
                "title": str(post["title"]),
                "excerpt": str(post["excerpt"]),
                "category": str(post["category"]),
                "author": str(post["author"]),
                "author_role": str(post["author_role"]),
                "content": str(post["content"]),
                "tags_json": json.dumps(list(post.get("tags") or []), ensure_ascii=False),
                "views": int(post.get("views") or 0),
                "read_time_minutes": int(post.get("read_time_minutes") or 3),
                "status": str(post.get("status") or "published"),
                "metadata_json": json.dumps(dict(post.get("metadata") or {}), ensure_ascii=False),
                "created_at": str(post.get("created_at") or now),
                "published_at": str(post.get("published_at") or now),
                "updated_at": str(post.get("updated_at") or now),
            },
        )


def load_blog_posts(
    *,
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
    status: str | None = None,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM blog_posts"
    params: list[Any] = []
    clauses: list[str] = []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
    params.extend([int(limit), int(offset)])
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return [_normalize_blog_row(dict(r)) for r in rows]


def count_blog_posts(*, category: str | None = None, status: str | None = None) -> int:
    query = "SELECT COUNT(*) AS c FROM blog_posts"
    params: list[Any] = []
    clauses: list[str] = []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    with get_db() as db:
        row = db.execute(query, params).fetchone()
    return int(row["c"] if row else 0)


def count_blog_posts_since(iso_timestamp: str) -> int:
    key = str(iso_timestamp or "").strip()
    if not key:
        return 0
    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM blog_posts WHERE published_at >= ?",
            (key,),
        ).fetchone()
    return int(row["c"] if row else 0)


def load_blog_post(post_id_or_slug: str) -> Dict[str, Any] | None:
    key = str(post_id_or_slug or "").strip()
    if not key:
        return None
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM blog_posts WHERE id = ? OR slug = ? LIMIT 1",
            (key, key),
        ).fetchone()
    return _normalize_blog_row(dict(row)) if row else None


def load_blog_post_by_source_report(report_id: str) -> Dict[str, Any] | None:
    key = str(report_id or "").strip()
    if not key:
        return None
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM blog_posts WHERE source_report_id = ? ORDER BY published_at DESC LIMIT 1",
            (key,),
        ).fetchone()
    return _normalize_blog_row(dict(row)) if row else None


def increment_blog_post_views(post_id: str, delta: int = 1) -> None:
    key = str(post_id or "").strip()
    if not key:
        return
    with get_db() as db:
        db.execute(
            "UPDATE blog_posts SET views = views + ?, updated_at = ? WHERE id = ?",
            (max(1, int(delta)), datetime.utcnow().isoformat(), key),
        )


def _normalize_blog_row(row: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed_tags = json.loads(row.get("tags_json") or "[]")
        tags = [str(item) for item in parsed_tags] if isinstance(parsed_tags, list) else []
    except Exception:
        tags = []
    try:
        parsed_metadata = json.loads(row.get("metadata_json") or "{}")
        metadata = parsed_metadata if isinstance(parsed_metadata, dict) else {}
    except Exception:
        metadata = {}
    row["tags"] = tags
    row["metadata"] = metadata
    row.pop("tags_json", None)
    row.pop("metadata_json", None)
    return row


# Fund task history
def save_task_history_event(event: Dict[str, Any]) -> None:
    row = dict(event or {})
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_task_history (
                task_id, run_id, agent_id, role, status, event, ts, priority, details_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row.get("task_id") or ""),
                row.get("run_id"),
                row.get("agent_id"),
                row.get("role"),
                row.get("status"),
                row.get("event"),
                str(row.get("ts") or datetime.utcnow().isoformat()),
                int(row["priority"]) if row.get("priority") is not None else None,
                json.dumps(row.get("details"), ensure_ascii=False) if row.get("details") is not None else None,
                json.dumps(row.get("payload"), ensure_ascii=False) if row.get("payload") is not None else None,
            ),
        )


def load_task_history_events(limit: int | None = None) -> List[Dict[str, Any]]:
    query = (
        "SELECT task_id, run_id, agent_id, role, status, event, ts, priority, details_json, payload_json "
        "FROM fund_task_history ORDER BY id ASC"
    )
    params: list[Any] = []
    if limit is not None and limit >= 0:
        query = (
            "SELECT * FROM ("
            "SELECT task_id, run_id, agent_id, role, status, event, ts, priority, details_json, payload_json "
            "FROM fund_task_history ORDER BY id DESC LIMIT ?"
            ") ORDER BY ts ASC"
        )
        params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()

    out: list[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        item: Dict[str, Any] = {
            "task_id": row.get("task_id"),
            "run_id": row.get("run_id"),
            "agent_id": row.get("agent_id"),
            "role": row.get("role"),
            "status": row.get("status"),
            "event": row.get("event"),
            "ts": row.get("ts"),
        }
        if row.get("priority") is not None:
            item["priority"] = int(row["priority"])
        details_raw = row.get("details_json")
        if details_raw:
            try:
                parsed = json.loads(details_raw)
                if isinstance(parsed, dict):
                    item["details"] = parsed
            except Exception:
                pass
        payload_raw = row.get("payload_json")
        if payload_raw:
            try:
                parsed = json.loads(payload_raw)
                if isinstance(parsed, dict):
                    item["payload"] = parsed
            except Exception:
                pass
        out.append(item)
    return out


# Decision ledger persistence
def save_decision_record(record: Dict[str, Any]) -> None:
    payload = dict(record or {})
    decision_id = str(payload.get("decision_id") or "").strip()
    if not decision_id:
        return
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_decisions (
                decision_id, run_id, status, sleeve, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(decision_id) DO UPDATE SET
                run_id=excluded.run_id,
                status=excluded.status,
                sleeve=excluded.sleeve,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                decision_id,
                payload.get("run_id"),
                str(payload.get("status") or "proposed"),
                payload.get("sleeve"),
                json.dumps(payload, ensure_ascii=False),
                now,
                now,
            ),
        )


def load_decision_records() -> List[Dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            """
            SELECT decision_id, payload_json
            FROM fund_decisions
            ORDER BY updated_at ASC, decision_id ASC
            """
        ).fetchall()
    out: list[Dict[str, Any]] = []
    for raw in rows:
        payload_raw = raw["payload_json"]
        if not payload_raw:
            continue
        try:
            payload = json.loads(payload_raw)
            if isinstance(payload, dict):
                out.append(payload)
        except Exception:
            continue
    return out


def save_decision_event(event: Dict[str, Any]) -> None:
    row = dict(event or {})
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        return
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_decision_events (
                event_id, event_type, decision_id, order_id, ts, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO NOTHING
            """,
            (
                event_id,
                str(row.get("event_type") or "unknown"),
                row.get("decision_id"),
                row.get("order_id"),
                str(row.get("ts") or datetime.utcnow().isoformat()),
                json.dumps(payload, ensure_ascii=False),
            ),
        )


def load_decision_events(limit: int | None = None) -> List[Dict[str, Any]]:
    query = (
        "SELECT event_id, event_type, decision_id, order_id, ts, payload_json "
        "FROM fund_decision_events ORDER BY id ASC"
    )
    params: list[Any] = []
    if limit is not None and limit >= 0:
        query = (
            "SELECT * FROM ("
            "SELECT event_id, event_type, decision_id, order_id, ts, payload_json "
            "FROM fund_decision_events ORDER BY id DESC LIMIT ?"
            ") ORDER BY ts ASC"
        )
        params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    out: list[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        payload: Dict[str, Any] = {}
        payload_raw = row.get("payload_json")
        if payload_raw:
            try:
                parsed = json.loads(payload_raw)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}
        out.append(
            {
                "event_id": row.get("event_id"),
                "event_type": row.get("event_type"),
                "decision_id": row.get("decision_id"),
                "order_id": row.get("order_id"),
                "ts": row.get("ts"),
                "payload": payload,
            }
        )
    return out


# Audit log persistence
def save_audit_event(event: Dict[str, Any]) -> None:
    row = dict(event or {})
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        return
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_audit_events (
                event_id, event_type, event_ts, run_id, decision_id, order_id, outcome, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO NOTHING
            """,
            (
                event_id,
                str(row.get("event_type") or "unknown"),
                str(row.get("event_ts") or datetime.utcnow().isoformat()),
                payload.get("run_id"),
                payload.get("decision_id"),
                payload.get("order_id"),
                payload.get("outcome"),
                json.dumps(payload, ensure_ascii=False),
            ),
        )


def load_audit_events(limit: int | None = None) -> List[Dict[str, Any]]:
    query = (
        "SELECT event_id, event_type, event_ts, payload_json "
        "FROM fund_audit_events ORDER BY id ASC"
    )
    params: list[Any] = []
    if limit is not None and limit >= 0:
        query = (
            "SELECT * FROM ("
            "SELECT event_id, event_type, event_ts, payload_json "
            "FROM fund_audit_events ORDER BY id DESC LIMIT ?"
            ") ORDER BY event_ts ASC"
        )
        params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    out: list[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        payload: Dict[str, Any] = {}
        payload_raw = row.get("payload_json")
        if payload_raw:
            try:
                parsed = json.loads(payload_raw)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}
        out.append(
            {
                "event_id": row.get("event_id"),
                "event_type": row.get("event_type"),
                "event_ts": row.get("event_ts"),
                "payload": payload,
            }
        )
    return out


# Research report persistence
def save_research_report(report: Dict[str, Any]) -> None:
    row = dict(report or {})
    report_id = str(row.get("report_id") or "").strip()
    if not report_id:
        return
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_research_reports (
                report_id, agent_id, created_at, assets_json, title, summary, thesis, confidence,
                provenance_json, tags_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
                agent_id=excluded.agent_id,
                created_at=excluded.created_at,
                assets_json=excluded.assets_json,
                title=excluded.title,
                summary=excluded.summary,
                thesis=excluded.thesis,
                confidence=excluded.confidence,
                provenance_json=excluded.provenance_json,
                tags_json=excluded.tags_json,
                metadata_json=excluded.metadata_json
            """,
            (
                report_id,
                str(row.get("agent_id") or "unknown"),
                str(row.get("created_at") or datetime.utcnow().isoformat()),
                json.dumps(list(row.get("assets") or []), ensure_ascii=False),
                str(row.get("title") or report_id),
                str(row.get("summary") or ""),
                row.get("thesis"),
                float(row.get("confidence") or 0.0),
                json.dumps(list(row.get("provenance") or []), ensure_ascii=False),
                json.dumps(list(row.get("tags") or []), ensure_ascii=False),
                json.dumps(dict(row.get("metadata") or {}), ensure_ascii=False),
            ),
        )


def load_research_reports(limit: int | None = None) -> List[Dict[str, Any]]:
    query = (
        "SELECT report_id, agent_id, created_at, assets_json, title, summary, thesis, confidence, "
        "provenance_json, tags_json, metadata_json "
        "FROM fund_research_reports ORDER BY created_at ASC"
    )
    params: list[Any] = []
    if limit is not None and limit >= 0:
        query = (
            "SELECT * FROM ("
            "SELECT report_id, agent_id, created_at, assets_json, title, summary, thesis, confidence, "
            "provenance_json, tags_json, metadata_json "
            "FROM fund_research_reports ORDER BY created_at DESC LIMIT ?"
            ") ORDER BY created_at ASC"
        )
        params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    out: list[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            assets = json.loads(row.get("assets_json") or "[]")
            if not isinstance(assets, list):
                assets = []
        except Exception:
            assets = []
        try:
            provenance = json.loads(row.get("provenance_json") or "[]")
            if not isinstance(provenance, list):
                provenance = []
        except Exception:
            provenance = []
        try:
            tags = json.loads(row.get("tags_json") or "[]")
            if not isinstance(tags, list):
                tags = []
        except Exception:
            tags = []
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}
        out.append(
            {
                "report_id": row.get("report_id"),
                "agent_id": row.get("agent_id"),
                "created_at": row.get("created_at"),
                "assets": assets,
                "title": row.get("title"),
                "summary": row.get("summary"),
                "thesis": row.get("thesis"),
                "confidence": float(row.get("confidence") or 0.0),
                "provenance": provenance,
                "tags": tags,
                "metadata": metadata,
            }
        )
    return out


# Sentiment snapshot persistence
def save_sentiment_snapshot(snapshot: Dict[str, Any]) -> None:
    row = dict(snapshot or {})
    snapshot_id = str(row.get("snapshot_id") or "").strip()
    if not snapshot_id:
        return
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_sentiment_snapshots (
                snapshot_id, asset, channel, text, sentiment_score, model_name,
                provenance_json, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                asset=excluded.asset,
                channel=excluded.channel,
                text=excluded.text,
                sentiment_score=excluded.sentiment_score,
                model_name=excluded.model_name,
                provenance_json=excluded.provenance_json,
                created_at=excluded.created_at,
                metadata_json=excluded.metadata_json
            """,
            (
                snapshot_id,
                str(row.get("asset") or ""),
                str(row.get("channel") or ""),
                str(row.get("text") or ""),
                float(row.get("sentiment_score") or 0.0),
                row.get("model_name"),
                json.dumps(dict(row.get("provenance") or {}), ensure_ascii=False),
                str(row.get("created_at") or datetime.utcnow().isoformat()),
                json.dumps(dict(row.get("metadata") or {}), ensure_ascii=False),
            ),
        )


def load_sentiment_snapshots(limit: int | None = None) -> List[Dict[str, Any]]:
    query = (
        "SELECT snapshot_id, asset, channel, text, sentiment_score, model_name, provenance_json, created_at, metadata_json "
        "FROM fund_sentiment_snapshots ORDER BY created_at ASC"
    )
    params: list[Any] = []
    if limit is not None and limit >= 0:
        query = (
            "SELECT * FROM ("
            "SELECT snapshot_id, asset, channel, text, sentiment_score, model_name, provenance_json, created_at, metadata_json "
            "FROM fund_sentiment_snapshots ORDER BY created_at DESC LIMIT ?"
            ") ORDER BY created_at ASC"
        )
        params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    out: list[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            provenance = json.loads(row.get("provenance_json") or "{}")
            if not isinstance(provenance, dict):
                provenance = {}
        except Exception:
            provenance = {}
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}
        out.append(
            {
                "snapshot_id": row.get("snapshot_id"),
                "asset": row.get("asset"),
                "channel": row.get("channel"),
                "text": row.get("text"),
                "sentiment_score": float(row.get("sentiment_score") or 0.0),
                "model_name": row.get("model_name"),
                "provenance": provenance,
                "created_at": row.get("created_at"),
                "metadata": metadata,
            }
        )
    return out


# Benchmark baseline persistence
def save_benchmark_baseline(symbol: str, baseline_price: float, baseline_at: str, metadata: Dict[str, Any] | None = None) -> None:
    key = str(symbol or "").strip().upper()
    if not key:
        return
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_benchmark_baselines (symbol, baseline_price, baseline_at, metadata_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                baseline_price=excluded.baseline_price,
                baseline_at=excluded.baseline_at,
                metadata_json=excluded.metadata_json
            """,
            (
                key,
                float(baseline_price),
                str(baseline_at or datetime.utcnow().isoformat()),
                json.dumps(dict(metadata or {}), ensure_ascii=False),
            ),
        )


def load_benchmark_baselines() -> Dict[str, Dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            "SELECT symbol, baseline_price, baseline_at, metadata_json FROM fund_benchmark_baselines ORDER BY symbol ASC"
        ).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}
        out[str(row.get("symbol") or "").upper()] = {
            "symbol": str(row.get("symbol") or "").upper(),
            "baseline_price": float(row.get("baseline_price") or 0.0),
            "baseline_at": row.get("baseline_at"),
            "metadata": metadata,
        }
    return out


# Performance snapshot persistence
def save_performance_snapshot(snapshot: Dict[str, Any]) -> None:
    row = dict(snapshot or {})
    snapshot_id = str(row.get("snapshot_id") or "").strip()
    if not snapshot_id:
        return
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_performance_snapshots (
                snapshot_id, snapshot_kind, recorded_at, broker_mode, equity, cash, market_value,
                realized_pnl, unrealized_pnl, total_pnl, total_trades, closed_trades, wins, losses,
                win_rate, max_drawdown, positions_json, benchmarks_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                snapshot_kind=excluded.snapshot_kind,
                recorded_at=excluded.recorded_at,
                broker_mode=excluded.broker_mode,
                equity=excluded.equity,
                cash=excluded.cash,
                market_value=excluded.market_value,
                realized_pnl=excluded.realized_pnl,
                unrealized_pnl=excluded.unrealized_pnl,
                total_pnl=excluded.total_pnl,
                total_trades=excluded.total_trades,
                closed_trades=excluded.closed_trades,
                wins=excluded.wins,
                losses=excluded.losses,
                win_rate=excluded.win_rate,
                max_drawdown=excluded.max_drawdown,
                positions_json=excluded.positions_json,
                benchmarks_json=excluded.benchmarks_json,
                metadata_json=excluded.metadata_json
            """,
            (
                snapshot_id,
                str(row.get("snapshot_kind") or "manual"),
                str(row.get("recorded_at") or datetime.utcnow().isoformat()),
                str(row.get("broker_mode") or "paper"),
                float(row.get("equity") or 0.0),
                float(row.get("cash") or 0.0),
                float(row.get("market_value") or 0.0),
                float(row.get("realized_pnl") or 0.0),
                float(row.get("unrealized_pnl") or 0.0),
                float(row.get("total_pnl") or 0.0),
                int(row.get("total_trades") or 0),
                int(row.get("closed_trades") or 0),
                int(row.get("wins") or 0),
                int(row.get("losses") or 0),
                float(row.get("win_rate") or 0.0),
                float(row.get("max_drawdown") or 0.0),
                json.dumps(list(row.get("positions") or []), ensure_ascii=False),
                json.dumps(list(row.get("benchmarks") or []), ensure_ascii=False),
                json.dumps(dict(row.get("metadata") or {}), ensure_ascii=False),
            ),
        )


def load_performance_snapshots(
    *,
    limit: int | None = None,
    snapshot_kind: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
) -> List[Dict[str, Any]]:
    query = (
        "SELECT snapshot_id, snapshot_kind, recorded_at, broker_mode, equity, cash, market_value, "
        "realized_pnl, unrealized_pnl, total_pnl, total_trades, closed_trades, wins, losses, "
        "win_rate, max_drawdown, positions_json, benchmarks_json, metadata_json "
        "FROM fund_performance_snapshots"
    )
    where: list[str] = []
    params: list[Any] = []
    if snapshot_kind:
        where.append("snapshot_kind = ?")
        params.append(str(snapshot_kind))
    if start_at:
        where.append("recorded_at >= ?")
        params.append(str(start_at))
    if end_at:
        where.append("recorded_at <= ?")
        params.append(str(end_at))
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY recorded_at ASC"
    if limit is not None and limit >= 0:
        query = f"SELECT * FROM ({query[:-len(' ORDER BY recorded_at ASC')]} ORDER BY recorded_at DESC LIMIT ?) ORDER BY recorded_at ASC"
        params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    out: List[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            positions = json.loads(row.get("positions_json") or "[]")
            if not isinstance(positions, list):
                positions = []
        except Exception:
            positions = []
        try:
            benchmarks = json.loads(row.get("benchmarks_json") or "[]")
            if not isinstance(benchmarks, list):
                benchmarks = []
        except Exception:
            benchmarks = []
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}
        out.append(
            {
                "snapshot_id": row.get("snapshot_id"),
                "snapshot_kind": row.get("snapshot_kind"),
                "recorded_at": row.get("recorded_at"),
                "broker_mode": row.get("broker_mode"),
                "equity": float(row.get("equity") or 0.0),
                "cash": float(row.get("cash") or 0.0),
                "market_value": float(row.get("market_value") or 0.0),
                "realized_pnl": float(row.get("realized_pnl") or 0.0),
                "unrealized_pnl": float(row.get("unrealized_pnl") or 0.0),
                "total_pnl": float(row.get("total_pnl") or 0.0),
                "total_trades": int(row.get("total_trades") or 0),
                "closed_trades": int(row.get("closed_trades") or 0),
                "wins": int(row.get("wins") or 0),
                "losses": int(row.get("losses") or 0),
                "win_rate": float(row.get("win_rate") or 0.0),
                "max_drawdown": float(row.get("max_drawdown") or 0.0),
                "positions": positions,
                "benchmarks": benchmarks,
                "metadata": metadata,
            }
        )
    return out


def load_latest_performance_snapshot(snapshot_kind: str | None = None) -> Dict[str, Any] | None:
    rows = load_performance_snapshots(limit=1, snapshot_kind=snapshot_kind)
    return rows[-1] if rows else None


def count_performance_snapshots(snapshot_kind: str | None = None) -> int:
    query = "SELECT COUNT(*) AS c FROM fund_performance_snapshots"
    params: list[Any] = []
    if snapshot_kind:
        query += " WHERE snapshot_kind = ?"
        params.append(str(snapshot_kind))
    with get_db() as db:
        row = db.execute(query, params).fetchone()
    return int(row["c"] if row else 0)


def clear_performance_history() -> Dict[str, int]:
    with get_db() as db:
        perf = db.execute("SELECT COUNT(*) AS c FROM fund_performance_snapshots").fetchone()
        bases = db.execute("SELECT COUNT(*) AS c FROM fund_benchmark_baselines").fetchone()
        deleted_snapshots = int(perf["c"] if perf else 0)
        deleted_baselines = int(bases["c"] if bases else 0)
        db.execute("DELETE FROM fund_performance_snapshots")
        db.execute("DELETE FROM fund_benchmark_baselines")
    return {
        "deleted_snapshots": deleted_snapshots,
        "deleted_baselines": deleted_baselines,
    }


# Allocation policy persistence
def save_allocation_policy(policy: Dict[str, Any]) -> None:
    row = dict(policy or {})
    policy_id = str(row.get("policy_id") or "").strip()
    if not policy_id:
        return
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_allocation_policies (
                policy_id, run_id, agent_id, status, total_capital_usd, reserve_cash_usd,
                deployable_capital_usd, asset_weights_json, sleeve_weights_json,
                constraints_json, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_id) DO UPDATE SET
                run_id=excluded.run_id,
                agent_id=excluded.agent_id,
                status=excluded.status,
                total_capital_usd=excluded.total_capital_usd,
                reserve_cash_usd=excluded.reserve_cash_usd,
                deployable_capital_usd=excluded.deployable_capital_usd,
                asset_weights_json=excluded.asset_weights_json,
                sleeve_weights_json=excluded.sleeve_weights_json,
                constraints_json=excluded.constraints_json,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            (
                policy_id,
                row.get("run_id"),
                row.get("agent_id"),
                str(row.get("status") or "active"),
                float(row.get("total_capital_usd") or 0.0),
                float(row.get("reserve_cash_usd") or 0.0),
                float(row.get("deployable_capital_usd") or 0.0),
                json.dumps(dict(row.get("asset_weights") or {}), ensure_ascii=False),
                json.dumps(dict(row.get("sleeve_weights") or {}), ensure_ascii=False),
                json.dumps(dict(row.get("constraints") or {}), ensure_ascii=False),
                json.dumps(dict(row.get("metadata") or {}), ensure_ascii=False),
                str(row.get("created_at") or now),
                str(row.get("updated_at") or now),
            ),
        )


def load_allocation_policies(*, limit: int = 20, run_id: str | None = None) -> List[Dict[str, Any]]:
    query = (
        "SELECT policy_id, run_id, agent_id, status, total_capital_usd, reserve_cash_usd, "
        "deployable_capital_usd, asset_weights_json, sleeve_weights_json, constraints_json, "
        "metadata_json, created_at, updated_at "
        "FROM fund_allocation_policies"
    )
    params: list[Any] = []
    if run_id:
        query += " WHERE run_id = ?"
        params.append(str(run_id))
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    out: List[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            asset_weights = json.loads(row.get("asset_weights_json") or "{}")
            if not isinstance(asset_weights, dict):
                asset_weights = {}
        except Exception:
            asset_weights = {}
        try:
            sleeve_weights = json.loads(row.get("sleeve_weights_json") or "{}")
            if not isinstance(sleeve_weights, dict):
                sleeve_weights = {}
        except Exception:
            sleeve_weights = {}
        try:
            constraints = json.loads(row.get("constraints_json") or "{}")
            if not isinstance(constraints, dict):
                constraints = {}
        except Exception:
            constraints = {}
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}
        out.append(
            {
                "policy_id": row.get("policy_id"),
                "run_id": row.get("run_id"),
                "agent_id": row.get("agent_id"),
                "status": row.get("status"),
                "total_capital_usd": float(row.get("total_capital_usd") or 0.0),
                "reserve_cash_usd": float(row.get("reserve_cash_usd") or 0.0),
                "deployable_capital_usd": float(row.get("deployable_capital_usd") or 0.0),
                "asset_weights": asset_weights,
                "sleeve_weights": sleeve_weights,
                "constraints": constraints,
                "metadata": metadata,
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }
        )
    return out


def load_latest_allocation_policy(run_id: str | None = None) -> Dict[str, Any] | None:
    rows = load_allocation_policies(limit=1, run_id=run_id)
    return rows[0] if rows else None


# Discovery opportunity persistence
def save_discovery_opportunity(opportunity: Dict[str, Any]) -> None:
    row = dict(opportunity or {})
    opportunity_id = str(row.get("opportunity_id") or "").strip()
    if not opportunity_id:
        return
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        db.execute(
            """
            INSERT INTO fund_discovery_opportunities (
                opportunity_id, run_id, symbol, asset_class, strategy_family, direction,
                score, confidence, horizon, thesis, catalysts_json, evidence_json, ml_json,
                metadata_json, status, discovered_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(opportunity_id) DO UPDATE SET
                run_id=excluded.run_id,
                symbol=excluded.symbol,
                asset_class=excluded.asset_class,
                strategy_family=excluded.strategy_family,
                direction=excluded.direction,
                score=excluded.score,
                confidence=excluded.confidence,
                horizon=excluded.horizon,
                thesis=excluded.thesis,
                catalysts_json=excluded.catalysts_json,
                evidence_json=excluded.evidence_json,
                ml_json=excluded.ml_json,
                metadata_json=excluded.metadata_json,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (
                opportunity_id,
                row.get("run_id"),
                str(row.get("symbol") or "").upper(),
                str(row.get("asset_class") or "equities"),
                row.get("strategy_family"),
                row.get("direction"),
                float(row.get("score") or 0.0),
                float(row.get("confidence") or 0.0),
                row.get("horizon"),
                str(row.get("thesis") or ""),
                json.dumps(list(row.get("catalysts") or []), ensure_ascii=False),
                json.dumps(list(row.get("evidence") or []), ensure_ascii=False),
                json.dumps(dict(row.get("ml") or {}), ensure_ascii=False),
                json.dumps(dict(row.get("metadata") or {}), ensure_ascii=False),
                str(row.get("status") or "candidate"),
                str(row.get("discovered_at") or now),
                str(row.get("updated_at") or now),
            ),
        )


def load_discovery_opportunities(
    *,
    limit: int = 100,
    run_id: str | None = None,
    status: str | None = None,
    asset_class: str | None = None,
) -> List[Dict[str, Any]]:
    query = (
        "SELECT opportunity_id, run_id, symbol, asset_class, strategy_family, direction, score, confidence, "
        "horizon, thesis, catalysts_json, evidence_json, ml_json, metadata_json, status, discovered_at, updated_at "
        "FROM fund_discovery_opportunities"
    )
    clauses: list[str] = []
    params: list[Any] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(str(run_id))
    if status:
        clauses.append("status = ?")
        params.append(str(status))
    if asset_class:
        clauses.append("asset_class = ?")
        params.append(str(asset_class))
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY score DESC, updated_at DESC LIMIT ?"
    params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    out: List[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            catalysts = json.loads(row.get("catalysts_json") or "[]")
            if not isinstance(catalysts, list):
                catalysts = []
        except Exception:
            catalysts = []
        try:
            evidence = json.loads(row.get("evidence_json") or "[]")
            if not isinstance(evidence, list):
                evidence = []
        except Exception:
            evidence = []
        try:
            ml = json.loads(row.get("ml_json") or "{}")
            if not isinstance(ml, dict):
                ml = {}
        except Exception:
            ml = {}
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}
        out.append(
            {
                "opportunity_id": row.get("opportunity_id"),
                "run_id": row.get("run_id"),
                "symbol": row.get("symbol"),
                "asset_class": row.get("asset_class"),
                "strategy_family": row.get("strategy_family"),
                "direction": row.get("direction"),
                "score": float(row.get("score") or 0.0),
                "confidence": float(row.get("confidence") or 0.0),
                "horizon": row.get("horizon"),
                "thesis": row.get("thesis"),
                "catalysts": catalysts,
                "evidence": evidence,
                "ml": ml,
                "metadata": metadata,
                "status": row.get("status"),
                "discovered_at": row.get("discovered_at"),
                "updated_at": row.get("updated_at"),
            }
        )
    return out


# Knowledge event persistence
def save_knowledge_event(event: Dict[str, Any]) -> None:
    row = dict(event or {})
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        return
    with get_db() as db:
        db.execute(
            """
            INSERT INTO knowledge_events (
                event_id, source, namespace, source_event_id, event_type, occurred_at,
                run_id, agent_id, decision_id, order_id, entities_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                source=excluded.source,
                namespace=excluded.namespace,
                source_event_id=excluded.source_event_id,
                event_type=excluded.event_type,
                occurred_at=excluded.occurred_at,
                run_id=excluded.run_id,
                agent_id=excluded.agent_id,
                decision_id=excluded.decision_id,
                order_id=excluded.order_id,
                entities_json=excluded.entities_json,
                payload_json=excluded.payload_json
            """,
            (
                event_id,
                str(row.get("source") or "unknown"),
                str(row.get("namespace") or "system"),
                row.get("source_event_id"),
                str(row.get("event_type") or "unknown"),
                str(row.get("occurred_at") or datetime.utcnow().isoformat()),
                row.get("run_id"),
                row.get("agent_id"),
                row.get("decision_id"),
                row.get("order_id"),
                json.dumps(dict(row.get("entities") or {}), ensure_ascii=False),
                json.dumps(dict(row.get("payload") or {}), ensure_ascii=False),
            ),
        )


def load_knowledge_events(limit: int | None = None) -> List[Dict[str, Any]]:
    query = (
        "SELECT event_id, source, namespace, source_event_id, event_type, occurred_at, "
        "run_id, agent_id, decision_id, order_id, entities_json, payload_json "
        "FROM knowledge_events ORDER BY occurred_at ASC, event_id ASC"
    )
    params: list[Any] = []
    if limit is not None and limit >= 0:
        query = (
            "SELECT * FROM ("
            "SELECT event_id, source, namespace, source_event_id, event_type, occurred_at, "
            "run_id, agent_id, decision_id, order_id, entities_json, payload_json "
            "FROM knowledge_events ORDER BY occurred_at DESC, event_id DESC LIMIT ?"
            ") ORDER BY occurred_at ASC, event_id ASC"
        )
        params.append(int(limit))
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    out: list[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            entities = json.loads(row.get("entities_json") or "{}")
            if not isinstance(entities, dict):
                entities = {}
        except Exception:
            entities = {}
        try:
            payload = json.loads(row.get("payload_json") or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        out.append(
            {
                "event_id": row.get("event_id"),
                "source": row.get("source"),
                "namespace": row.get("namespace"),
                "source_event_id": row.get("source_event_id"),
                "event_type": row.get("event_type"),
                "occurred_at": row.get("occurred_at"),
                "run_id": row.get("run_id"),
                "agent_id": row.get("agent_id"),
                "decision_id": row.get("decision_id"),
                "order_id": row.get("order_id"),
                "entities": entities,
                "payload": payload,
            }
        )
    return out


def clear_knowledge_events() -> int:
    with get_db() as db:
        row = db.execute("SELECT COUNT(*) AS c FROM knowledge_events").fetchone()
        deleted = int(row["c"] if row else 0)
        db.execute("DELETE FROM knowledge_events")
    return deleted
