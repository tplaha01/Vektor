from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402


DEFAULT_TABLES = [
    "positions",
    "orders",
    "cash_snapshots",
    "data_market_bars",
    "data_feature_vectors",
    "data_pipeline_runs",
    "data_provider_health",
    "fund_performance_snapshots",
]


def _mask_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        username = parts.username or ""
        auth = f"{username}:***@" if username else ""
        return urlunsplit((parts.scheme, f"{auth}{host}{port}", parts.path, "", ""))
    except Exception:
        return "***"


def _sqlite_conn(path: str) -> sqlite3.Connection:
    if path != ":memory:" and not Path(path).exists():
        raise SystemExit(f"SQLite database not found: {Path(path).resolve()}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _postgres_conn(url: str):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(url, row_factory=dict_row)


def _tables(conn: Any, backend: str) -> list[str]:
    if backend == "postgres":
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            return [str(row["table_name"]) for row in cur.fetchall()]
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [str(row["name"]) for row in rows]


def _count(conn: Any, backend: str, table: str) -> int:
    if backend == "postgres":
        with conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) AS c FROM "{table}"')
            row = cur.fetchone()
            return int(row["c"] if row else 0)
    row = conn.execute(f'SELECT COUNT(*) AS c FROM "{table}"').fetchone()
    return int(row["c"] if row else 0)


def _latest(conn: Any, backend: str, table: str, limit: int) -> list[dict[str, Any]]:
    order_by = {
        "orders": "created_at",
        "cash_snapshots": "recorded_at",
        "data_market_bars": "ts",
        "data_feature_vectors": "created_at",
        "data_pipeline_runs": "started_at",
        "data_provider_health": "updated_at",
        "fund_performance_snapshots": "recorded_at",
    }.get(table)
    if backend == "postgres":
        with conn.cursor() as cur:
            if order_by:
                cur.execute(f'SELECT * FROM "{table}" ORDER BY "{order_by}" DESC LIMIT %s', (limit,))
            else:
                cur.execute(f'SELECT * FROM "{table}" LIMIT %s', (limit,))
            return [dict(row) for row in cur.fetchall()]
    if order_by:
        rows = conn.execute(f'SELECT * FROM "{table}" ORDER BY "{order_by}" DESC LIMIT ?', (limit,)).fetchall()
    else:
        rows = conn.execute(f'SELECT * FROM "{table}" LIMIT ?', (limit,)).fetchall()
    return [dict(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only backend database inspector.")
    parser.add_argument("--backend", choices=["auto", "sqlite", "postgres"], default="auto")
    parser.add_argument("--sqlite-path", default=None)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--table", action="append", default=[])
    parser.add_argument("--latest", default=None, help="Print latest rows for one table")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    backend = args.backend if args.backend != "auto" else (settings.DB_BACKEND or "sqlite").lower()
    backend = "postgres" if backend in {"postgresql", "postgres"} else "sqlite"
    sqlite_path = args.sqlite_path or settings.SQLITE_PATH
    database_url = args.database_url or settings.DATABASE_URL or os.getenv("DATABASE_URL")

    if backend == "postgres":
        if not database_url:
            raise SystemExit("DATABASE_URL is required for postgres inspection")
        conn = _postgres_conn(database_url)
        location = _mask_url(database_url)
    else:
        conn = _sqlite_conn(sqlite_path)
        location = str(Path(sqlite_path).resolve())

    try:
        table_names = _tables(conn, backend)
        selected = args.table or [t for t in DEFAULT_TABLES if t in table_names]
        payload = {
            "backend": backend,
            "location": location,
            "tables": table_names,
            "counts": {table: _count(conn, backend, table) for table in selected if table in table_names},
        }
        if args.latest:
            if args.latest not in table_names:
                raise SystemExit(f"Unknown table: {args.latest}")
            payload["latest"] = {
                "table": args.latest,
                "rows": _latest(conn, backend, args.latest, max(1, int(args.limit))),
            }

        if args.json:
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(f"backend: {payload['backend']}")
            print(f"location: {payload['location']}")
            print("counts:")
            for table, count in payload["counts"].items():
                print(f"  {table}: {count}")
            if "latest" in payload:
                print("latest:")
                print(json.dumps(payload["latest"], indent=2, default=str))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
