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

CREATE TABLE IF NOT EXISTS fund_task_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT NOT NULL,
    run_id       TEXT,
    agent_id     TEXT,
    role         TEXT,
    status       TEXT,
    event        TEXT,
    ts           TEXT NOT NULL,
    priority     INTEGER,
    details_json TEXT,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_fund_task_history_run_ts ON fund_task_history (run_id, ts);
CREATE INDEX IF NOT EXISTS idx_fund_task_history_task ON fund_task_history (task_id);
CREATE INDEX IF NOT EXISTS idx_fund_task_history_role_status ON fund_task_history (role, status);

CREATE TABLE IF NOT EXISTS blog_posts (
    id               TEXT PRIMARY KEY,
    source_report_id TEXT,
    source_run_id    TEXT,
    slug             TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    excerpt          TEXT NOT NULL,
    category         TEXT NOT NULL,
    author           TEXT NOT NULL,
    author_role      TEXT NOT NULL,
    content          TEXT NOT NULL,
    tags_json        TEXT NOT NULL,
    views            INTEGER NOT NULL DEFAULT 0,
    read_time_minutes INTEGER NOT NULL DEFAULT 3,
    status           TEXT NOT NULL DEFAULT 'published',
    metadata_json    TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    published_at     TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_blog_posts_published_at ON blog_posts (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_blog_posts_category ON blog_posts (category);
CREATE INDEX IF NOT EXISTS idx_blog_posts_source_report_id ON blog_posts (source_report_id);
"""
