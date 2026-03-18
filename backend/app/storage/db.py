from __future__ import annotations

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
        raise RuntimeError("Database not initialised — call init_db() at startup")
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
    print(f"💾 Database initialised at {settings.SQLITE_PATH}")


@contextmanager
def get_db():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── Orders ────────────────────────────────────────────────────────────────────

def save_order(order: Dict[str, Any]) -> None:
    with get_db() as db:
        db.execute(
            """INSERT OR REPLACE INTO orders
               (id, symbol, side, qty, avg_price, status, created_at)
               VALUES (:id, :symbol, :side, :qty, :avg_price, :status, :created_at)""",
            {
                "id":        str(order["id"]),
                "symbol":    order["symbol"],
                "side":      order["side"],
                "qty":       float(order["qty"]),
                "avg_price": float(order.get("avg_price", order.get("price", 0))),
                "status":    order.get("status", "filled"),
                "created_at": order.get("created_at", datetime.utcnow().isoformat()),
            },
        )


def load_orders() -> List[Dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM orders ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]


# ── Positions ─────────────────────────────────────────────────────────────────

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


# ── Cash ──────────────────────────────────────────────────────────────────────

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
