SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    qty         REAL NOT NULL,
    avg_price   REAL NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    symbol      TEXT PRIMARY KEY,
    qty         REAL NOT NULL,
    avg_price   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cash_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cash        REAL NOT NULL,
    recorded_at TEXT NOT NULL
);
"""
