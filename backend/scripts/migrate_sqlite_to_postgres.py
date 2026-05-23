from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.storage.db import to_postgres_schema_sql
from app.storage.schema_sql import SCHEMA_SQL


def _quote_ident(name: str) -> str:
    if not name.replace("_", "").isalnum() or not name[0].isalpha():
        raise ValueError(f"unsafe identifier: {name!r}")
    return f'"{name}"'


def _sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()]


def _primary_key_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()
    keyed = [(int(row[5]), str(row[1])) for row in rows if int(row[5] or 0) > 0]
    return [name for _, name in sorted(keyed)]


def _chunks(rows: list[sqlite3.Row], size: int) -> Iterable[list[sqlite3.Row]]:
    for idx in range(0, len(rows), size):
        yield rows[idx : idx + size]


def _create_schema(pg_conn: Any) -> None:
    schema_sql = to_postgres_schema_sql(SCHEMA_SQL)
    with pg_conn.cursor() as cur:
        for statement in [part.strip() for part in schema_sql.split(";") if part.strip()]:
            cur.execute(statement)
    pg_conn.commit()


def _copy_table(
    *,
    sqlite_conn: sqlite3.Connection,
    pg_conn: Any,
    table: str,
    batch_size: int,
) -> int:
    columns = _table_columns(sqlite_conn, table)
    if not columns:
        return 0
    pk_columns = _primary_key_columns(sqlite_conn, table)
    quoted_columns = ", ".join(_quote_ident(col) for col in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    table_ident = _quote_ident(table)
    sql = f"INSERT INTO {table_ident} ({quoted_columns}) VALUES ({placeholders})"
    if pk_columns:
        update_columns = [col for col in columns if col not in set(pk_columns)]
        conflict_target = ", ".join(_quote_ident(col) for col in pk_columns)
        if update_columns:
            assignments = ", ".join(f"{_quote_ident(col)} = EXCLUDED.{_quote_ident(col)}" for col in update_columns)
            sql += f" ON CONFLICT ({conflict_target}) DO UPDATE SET {assignments}"
        else:
            sql += f" ON CONFLICT ({conflict_target}) DO NOTHING"
    else:
        sql += " ON CONFLICT DO NOTHING"

    rows = sqlite_conn.execute(f"SELECT {quoted_columns} FROM {table_ident}").fetchall()
    copied = 0
    with pg_conn.cursor() as cur:
        for batch in _chunks(rows, batch_size):
            cur.executemany(sql, [tuple(row[col] for col in columns) for row in batch])
            copied += len(batch)
    pg_conn.commit()
    return copied


def _truncate_tables(pg_conn: Any, tables: list[str]) -> None:
    if not tables:
        return
    table_list = ", ".join(_quote_ident(table) for table in tables)
    with pg_conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")
    pg_conn.commit()


def _reset_sequences(pg_conn: Any, tables: list[str]) -> None:
    with pg_conn.cursor() as cur:
        for table in tables:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_default LIKE 'nextval%%'
                """,
                (table,),
            )
            for (column_name,) in cur.fetchall():
                cur.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, %s), COALESCE((SELECT MAX(%s) FROM %s), 1), true)"
                    % ("%s", "%s", _quote_ident(column_name), _quote_ident(table)),
                    (table, column_name),
                )
    pg_conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate the Vektor SQLite database into hosted Postgres.")
    parser.add_argument("--sqlite-path", default="trading_bot.db", help="Path to the source SQLite database.")
    parser.add_argument("--database-url", required=True, help="Destination Postgres DATABASE_URL.")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--truncate-target", action="store_true", help="Clear target tables before copying.")
    parser.add_argument(
        "--tables",
        nargs="*",
        default=None,
        help="Optional table allowlist. When omitted, all SQLite tables are copied.",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")

    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install psycopg first: py -3 -m pip install 'psycopg[binary]==3.2.3'") from exc

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg.connect(args.database_url)
    try:
        _create_schema(pg_conn)
        tables = _sqlite_tables(sqlite_conn)
        if args.tables:
            requested = [str(table) for table in args.tables]
            missing = sorted(set(requested) - set(tables))
            if missing:
                raise SystemExit(f"Requested table(s) not found in SQLite database: {', '.join(missing)}")
            tables = [table for table in tables if table in set(requested)]
        if args.truncate_target:
            _truncate_tables(pg_conn, tables)
        total = 0
        for table in tables:
            copied = _copy_table(
                sqlite_conn=sqlite_conn,
                pg_conn=pg_conn,
                table=table,
                batch_size=max(1, int(args.batch_size)),
            )
            total += copied
            print(f"{table}: {copied}")
        _reset_sequences(pg_conn, tables)
        print(f"migration_complete tables={len(tables)} rows={total}")
    finally:
        sqlite_conn.close()
        pg_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
