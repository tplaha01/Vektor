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

CREATE TABLE IF NOT EXISTS fund_decisions (
    decision_id   TEXT PRIMARY KEY,
    run_id        TEXT,
    status        TEXT NOT NULL,
    sleeve        TEXT,
    payload_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_decisions_run_status ON fund_decisions (run_id, status);

CREATE TABLE IF NOT EXISTS fund_decision_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT NOT NULL UNIQUE,
    event_type   TEXT NOT NULL,
    decision_id  TEXT,
    order_id     TEXT,
    ts           TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_decision_events_decision_ts ON fund_decision_events (decision_id, ts);
CREATE INDEX IF NOT EXISTS idx_fund_decision_events_order_ts ON fund_decision_events (order_id, ts);

CREATE TABLE IF NOT EXISTS fund_audit_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT NOT NULL UNIQUE,
    event_type   TEXT NOT NULL,
    event_ts     TEXT NOT NULL,
    run_id       TEXT,
    decision_id  TEXT,
    order_id     TEXT,
    outcome      TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_audit_events_order_ts ON fund_audit_events (order_id, event_ts);
CREATE INDEX IF NOT EXISTS idx_fund_audit_events_decision_ts ON fund_audit_events (decision_id, event_ts);
CREATE INDEX IF NOT EXISTS idx_fund_audit_events_run_ts ON fund_audit_events (run_id, event_ts);

CREATE TABLE IF NOT EXISTS fund_research_reports (
    report_id        TEXT PRIMARY KEY,
    agent_id         TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    assets_json      TEXT NOT NULL,
    title            TEXT NOT NULL,
    summary          TEXT NOT NULL,
    thesis           TEXT,
    confidence       REAL NOT NULL,
    provenance_json  TEXT NOT NULL,
    tags_json        TEXT NOT NULL,
    metadata_json    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_research_reports_created_at ON fund_research_reports (created_at DESC);

CREATE TABLE IF NOT EXISTS fund_sentiment_snapshots (
    snapshot_id      TEXT PRIMARY KEY,
    asset            TEXT NOT NULL,
    channel          TEXT NOT NULL,
    text             TEXT NOT NULL,
    sentiment_score  REAL NOT NULL,
    model_name       TEXT,
    provenance_json  TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    metadata_json    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_sentiment_asset_created ON fund_sentiment_snapshots (asset, created_at DESC);

CREATE TABLE IF NOT EXISTS fund_benchmark_baselines (
    symbol          TEXT PRIMARY KEY,
    baseline_price  REAL NOT NULL,
    baseline_at     TEXT NOT NULL,
    metadata_json   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fund_performance_snapshots (
    snapshot_id        TEXT PRIMARY KEY,
    snapshot_kind      TEXT NOT NULL,
    recorded_at        TEXT NOT NULL,
    broker_mode        TEXT NOT NULL,
    equity             REAL NOT NULL,
    cash               REAL NOT NULL,
    market_value       REAL NOT NULL,
    realized_pnl       REAL NOT NULL,
    unrealized_pnl     REAL NOT NULL,
    total_pnl          REAL NOT NULL,
    total_trades       INTEGER NOT NULL,
    closed_trades      INTEGER NOT NULL,
    wins               INTEGER NOT NULL,
    losses             INTEGER NOT NULL,
    win_rate           REAL NOT NULL,
    max_drawdown       REAL NOT NULL,
    positions_json     TEXT NOT NULL,
    benchmarks_json    TEXT NOT NULL,
    metadata_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_performance_snapshots_recorded_at
ON fund_performance_snapshots (recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_fund_performance_snapshots_kind_recorded_at
ON fund_performance_snapshots (snapshot_kind, recorded_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_events (
    event_id         TEXT PRIMARY KEY,
    source           TEXT NOT NULL,
    namespace        TEXT NOT NULL,
    source_event_id  TEXT,
    event_type       TEXT NOT NULL,
    occurred_at      TEXT NOT NULL,
    run_id           TEXT,
    agent_id         TEXT,
    decision_id      TEXT,
    order_id         TEXT,
    entities_json    TEXT NOT NULL,
    payload_json     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_events_occurred_at ON knowledge_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_events_namespace_ts ON knowledge_events (namespace, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_events_run_ts ON knowledge_events (run_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_events_decision_ts ON knowledge_events (decision_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_events_order_ts ON knowledge_events (order_id, occurred_at DESC);
"""
