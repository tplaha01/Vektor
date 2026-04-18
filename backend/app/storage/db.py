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
    _conn.commit()
    print(f"Database initialized at {settings.SQLITE_PATH}")


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
               (id, symbol, side, qty, avg_price, status, created_at)
               VALUES (:id, :symbol, :side, :qty, :avg_price, :status, :created_at)""",
            {
                "id": str(order["id"]),
                "symbol": order["symbol"],
                "side": order["side"],
                "qty": float(order["qty"]),
                "avg_price": float(order.get("avg_price", order.get("price", 0))),
                "status": order.get("status", "filled"),
                "created_at": order.get("created_at", datetime.utcnow().isoformat()),
            },
        )


def load_orders() -> List[Dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM orders ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]


# Positions
def save_positions(positions: Dict[str, Dict]) -> None:
    """Replaces entire positions table with current in-memory state."""
    with get_db() as db:
        db.execute("DELETE FROM positions")
        for sym, pos in positions.items():
            db.execute(
                "INSERT INTO positions (symbol, qty, avg_price) VALUES (?, ?, ?)",
                (sym, float(pos["qty"]), float(pos["avg_price"])),
            )


def load_positions() -> Dict[str, Dict]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM positions").fetchall()
        return {
            r["symbol"]: {"symbol": r["symbol"], "qty": r["qty"], "avg_price": r["avg_price"]}
            for r in rows
        }


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


def load_blog_posts(*, limit: int = 50, offset: int = 0, category: str | None = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM blog_posts"
    params: list[Any] = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
    params.extend([int(limit), int(offset)])
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return [_normalize_blog_row(dict(r)) for r in rows]


def count_blog_posts(*, category: str | None = None) -> int:
    query = "SELECT COUNT(*) AS c FROM blog_posts"
    params: list[Any] = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
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
