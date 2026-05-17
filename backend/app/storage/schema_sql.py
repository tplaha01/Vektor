SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    qty         REAL NOT NULL,
    avg_price   REAL NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    asset_class TEXT,
    instrument_type TEXT,
    routing_mode TEXT,
    underlier_symbol TEXT,
    contract_multiplier REAL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS positions (
    symbol      TEXT PRIMARY KEY,
    qty         REAL NOT NULL,
    avg_price   REAL NOT NULL,
    asset_class TEXT,
    instrument_type TEXT,
    routing_mode TEXT,
    underlier_symbol TEXT,
    contract_multiplier REAL,
    metadata_json TEXT
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

CREATE TABLE IF NOT EXISTS fund_approval_requests (
    request_id        TEXT PRIMARY KEY,
    run_id            TEXT,
    request_type      TEXT NOT NULL,
    subject_id        TEXT,
    requested_by      TEXT NOT NULL,
    status            TEXT NOT NULL,
    summary           TEXT NOT NULL,
    payload_json      TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    expires_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_fund_approval_requests_status_created
ON fund_approval_requests (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fund_approval_requests_run_type
ON fund_approval_requests (run_id, request_type, updated_at DESC);

CREATE TABLE IF NOT EXISTS fund_ceo_digests (
    digest_id         TEXT PRIMARY KEY,
    digest_type       TEXT NOT NULL,
    generated_by      TEXT NOT NULL,
    payload_json      TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_ceo_digests_created
ON fund_ceo_digests (created_at DESC);

CREATE TABLE IF NOT EXISTS fund_post_trade_reviews (
    review_id          TEXT PRIMARY KEY,
    symbol             TEXT NOT NULL,
    decision_id        TEXT,
    order_id           TEXT,
    asset_class        TEXT NOT NULL,
    thesis_state       TEXT NOT NULL,
    review_status      TEXT NOT NULL,
    risk_flags_json    TEXT NOT NULL,
    payload_json       TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_post_trade_reviews_symbol_created
ON fund_post_trade_reviews (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fund_post_trade_reviews_state_created
ON fund_post_trade_reviews (thesis_state, created_at DESC);

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

CREATE TABLE IF NOT EXISTS fund_allocation_policies (
    policy_id             TEXT PRIMARY KEY,
    run_id                TEXT,
    agent_id              TEXT,
    status                TEXT NOT NULL,
    total_capital_usd     REAL NOT NULL,
    reserve_cash_usd      REAL NOT NULL,
    deployable_capital_usd REAL NOT NULL,
    asset_weights_json    TEXT NOT NULL,
    sleeve_weights_json   TEXT NOT NULL,
    constraints_json      TEXT NOT NULL,
    metadata_json         TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_allocation_policies_run_updated
ON fund_allocation_policies (run_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS fund_discovery_opportunities (
    opportunity_id      TEXT PRIMARY KEY,
    run_id              TEXT,
    symbol              TEXT NOT NULL,
    asset_class         TEXT NOT NULL,
    strategy_family     TEXT,
    direction           TEXT,
    score               REAL NOT NULL,
    confidence          REAL NOT NULL,
    horizon             TEXT,
    thesis              TEXT NOT NULL,
    catalysts_json      TEXT NOT NULL,
    evidence_json       TEXT NOT NULL,
    ml_json             TEXT NOT NULL,
    metadata_json       TEXT NOT NULL,
    status              TEXT NOT NULL,
    discovered_at       TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_discovery_opportunities_run_updated
ON fund_discovery_opportunities (run_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_fund_discovery_opportunities_status_score
ON fund_discovery_opportunities (status, score DESC);

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

CREATE TABLE IF NOT EXISTS data_raw_events (
    raw_id             TEXT PRIMARY KEY,
    provider           TEXT NOT NULL,
    endpoint           TEXT NOT NULL,
    asset_class        TEXT NOT NULL,
    symbol             TEXT,
    request_json       TEXT NOT NULL,
    payload_json       TEXT NOT NULL,
    payload_checksum   TEXT NOT NULL,
    provider_ts        TEXT,
    ingested_at        TEXT NOT NULL,
    metadata_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_raw_events_provider_ingested
ON data_raw_events (provider, ingested_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_raw_events_symbol_ingested
ON data_raw_events (symbol, ingested_at DESC);

CREATE TABLE IF NOT EXISTS data_market_bars (
    symbol             TEXT NOT NULL,
    asset_class        TEXT NOT NULL,
    timeframe          TEXT NOT NULL,
    ts                 TEXT NOT NULL,
    open               REAL NOT NULL,
    high               REAL NOT NULL,
    low                REAL NOT NULL,
    close              REAL NOT NULL,
    volume             REAL NOT NULL,
    provider           TEXT NOT NULL,
    raw_id             TEXT,
    adjusted           INTEGER NOT NULL DEFAULT 0,
    quality_score      REAL NOT NULL DEFAULT 0,
    quality_flags_json TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    PRIMARY KEY (symbol, timeframe, ts, provider)
);

CREATE INDEX IF NOT EXISTS idx_data_market_bars_symbol_tf_ts
ON data_market_bars (symbol, timeframe, ts DESC);

CREATE TABLE IF NOT EXISTS data_market_prices (
    symbol             TEXT NOT NULL,
    asset_class        TEXT NOT NULL,
    price              REAL NOT NULL,
    provider           TEXT NOT NULL,
    source_mode        TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    raw_id             TEXT,
    quality_score      REAL NOT NULL DEFAULT 0,
    quality_flags_json TEXT NOT NULL,
    PRIMARY KEY (symbol, provider, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_data_market_prices_symbol_observed
ON data_market_prices (symbol, observed_at DESC);

CREATE TABLE IF NOT EXISTS data_market_quotes (
    symbol             TEXT NOT NULL,
    asset_class        TEXT NOT NULL,
    bid_price          REAL NOT NULL,
    bid_size           REAL,
    ask_price          REAL NOT NULL,
    ask_size           REAL,
    mid_price          REAL NOT NULL,
    spread             REAL NOT NULL,
    spread_bps         REAL NOT NULL,
    provider           TEXT NOT NULL,
    source_mode        TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    raw_id             TEXT,
    quality_score      REAL NOT NULL DEFAULT 0,
    quality_flags_json TEXT NOT NULL,
    PRIMARY KEY (symbol, provider, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_data_market_quotes_symbol_observed
ON data_market_quotes (symbol, observed_at DESC);

CREATE TABLE IF NOT EXISTS data_text_events (
    event_id           TEXT PRIMARY KEY,
    symbol             TEXT,
    asset_class        TEXT NOT NULL,
    source_type        TEXT NOT NULL,
    provider           TEXT NOT NULL,
    title              TEXT NOT NULL,
    body               TEXT,
    url                TEXT,
    published_at       TEXT,
    ingested_at        TEXT NOT NULL,
    raw_id             TEXT,
    sentiment_score    REAL,
    quality_score      REAL NOT NULL DEFAULT 0,
    quality_flags_json TEXT NOT NULL,
    metadata_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_text_events_symbol_published
ON data_text_events (symbol, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_text_events_provider_ingested
ON data_text_events (provider, ingested_at DESC);

CREATE TABLE IF NOT EXISTS data_fundamentals (
    symbol             TEXT NOT NULL,
    asset_class        TEXT NOT NULL,
    provider           TEXT NOT NULL,
    metric_date        TEXT NOT NULL,
    period             TEXT NOT NULL,
    metrics_json       TEXT NOT NULL,
    raw_id             TEXT,
    quality_score      REAL NOT NULL DEFAULT 0,
    quality_flags_json TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    PRIMARY KEY (symbol, provider, metric_date, period)
);

CREATE INDEX IF NOT EXISTS idx_data_fundamentals_symbol_date
ON data_fundamentals (symbol, metric_date DESC);

CREATE TABLE IF NOT EXISTS data_quality_events (
    quality_id         TEXT PRIMARY KEY,
    dataset            TEXT NOT NULL,
    symbol             TEXT,
    provider           TEXT NOT NULL,
    score              REAL NOT NULL,
    flags_json         TEXT NOT NULL,
    severity           TEXT NOT NULL,
    checked_at         TEXT NOT NULL,
    metadata_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_quality_events_dataset_checked
ON data_quality_events (dataset, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_quality_events_symbol_checked
ON data_quality_events (symbol, checked_at DESC);

CREATE TABLE IF NOT EXISTS data_feature_vectors (
    feature_id         TEXT PRIMARY KEY,
    symbol             TEXT NOT NULL,
    asset_class        TEXT NOT NULL,
    use_case           TEXT NOT NULL,
    as_of              TEXT NOT NULL,
    features_json      TEXT NOT NULL,
    score              REAL NOT NULL,
    category           TEXT NOT NULL,
    source_snapshot_id TEXT NOT NULL,
    metadata_json      TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_feature_vectors_symbol_use_case_asof
ON data_feature_vectors (symbol, use_case, as_of DESC);

CREATE TABLE IF NOT EXISTS data_pipeline_runs (
    run_id             TEXT PRIMARY KEY,
    run_type           TEXT NOT NULL,
    status             TEXT NOT NULL,
    started_at         TEXT NOT NULL,
    finished_at        TEXT,
    symbols_json       TEXT NOT NULL,
    counts_json        TEXT NOT NULL,
    quality_json       TEXT NOT NULL,
    metadata_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_pipeline_runs_started
ON data_pipeline_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS data_provider_health (
    provider           TEXT PRIMARY KEY,
    status             TEXT NOT NULL,
    last_event_at      TEXT,
    last_success_at    TEXT,
    last_failure_at    TEXT,
    success_count      INTEGER NOT NULL DEFAULT 0,
    failure_count      INTEGER NOT NULL DEFAULT 0,
    stale_count        INTEGER NOT NULL DEFAULT 0,
    last_error         TEXT,
    metadata_json      TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_provider_health_status_updated
ON data_provider_health (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS data_snapshots (
    snapshot_id        TEXT PRIMARY KEY,
    snapshot_type      TEXT NOT NULL,
    symbol             TEXT,
    as_of              TEXT NOT NULL,
    source_ids_json    TEXT NOT NULL,
    payload_json       TEXT NOT NULL,
    quality_json       TEXT NOT NULL,
    metadata_json      TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_snapshots_symbol_asof
ON data_snapshots (symbol, as_of DESC);
CREATE INDEX IF NOT EXISTS idx_data_snapshots_type_created
ON data_snapshots (snapshot_type, created_at DESC);
"""
