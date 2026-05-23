# Vektor Technical Handbook

As of: 2026-05-22  
Repository: `TradingBot`

## 1. What This Book Is

This is the technical map of Vektor as it exists in this repository today.

Its purpose is to answer four questions:

1. What Vektor is trying to become.
2. What is already real in code.
3. Where each responsibility lives in the stack.
4. How to read the repo without getting lost.

This handbook is based on the actual repo structure, the current indexed code graph, and the current source-of-truth repo docs:

- `Vektor.md`
- `DevViktor.md`
- `docs/VEKTOR_PHASED_EXECUTION_PLAN.md`
- `docs/AI_NATIVE_HEDGE_FUND_AUDIT_AND_ROADMAP.md`

It is not a marketing summary. It is a technical field manual.

## 2. Executive Summary

Vektor started as a relatively compact hybrid paper-trading bot and is being expanded into a paper-first AI-native hedge fund operating system.

The current codebase has three layers living at once:

1. Legacy trading bot core.
   It still has a direct FastAPI app, a paper broker, a hybrid signal function, a risk engine, a websocket stream, and a backtest engine.
2. Quant and data foundation.
   It now has a local-first quant data pipeline, warehouse tables, provider health tracking, feature-vector generation, regime logic, and a LightGBM alpha path.
3. Fund operating system overlay.
   It now also has fund contracts, orchestration, task routing, approvals, audit logging, research memory, a knowledge graph, admin endpoints, OpenClaw command ingestion, and an operator UI.

The important reality is this:

- Vektor is already more than a toy bot.
- It is not yet the final multi-agent institutional platform described in `Vektor.md`.
- The repo currently contains both mature working flows and forward-looking scaffolding.

## 3. Past To Present

### 3.1 Original Identity

The oldest stable core of the repo is a "Hybrid Trading Bot":

- FastAPI backend
- React/Vite frontend
- Paper-only broker
- Technical + fundamental + sentiment + optional ML signal generation
- Basic risk checks
- SQLite persistence

That layer is still visible in:

- `backend/app/main.py`
- `backend/app/strategies/hybrid.py`
- `backend/app/strategies/auto_trader.py`
- `backend/app/broker/paper.py`
- `backend/app/risk/engine.py`
- `frontend/src/api.js`
- `frontend/src/components/*`

### 3.2 Strategic Reframe Into Vektor

`Vektor.md` changes the system from "single trading bot" to "firm operating system". The target model becomes:

- research -> thesis -> risk -> execution -> audit -> learning
- role-specialized agents
- knowledge graph persistence
- sleeve budgets and allocation policy
- operator control
- paper-first institutional workflow

This is why the repo now has a large `backend/app/fund/` package and a large admin surface.

### 3.3 Current State

Today Vektor is a hybrid of:

- a functioning paper-trading application
- a growing data and quant platform
- a partial but serious fund orchestration system

The code is backend-first. The repo's own phased plan explicitly says not to treat UI polish as the core of the system while backend truth is still evolving.

## 4. Repo Topography

At the highest level the repo contains four application surfaces:

| Area | Purpose |
| --- | --- |
| `backend/` | FastAPI backend, quant, paper broker, fund orchestration, storage, knowledge graph, admin API |
| `frontend/` | Main operator/product React app built with Vite |
| `landing-next/` | Public marketing/landing site built with Next.js |
| `blog-next/` | Separate Next/Fumadocs blog-docs app/template |

Supporting areas:

| Area | Purpose |
| --- | --- |
| `docs/` | architecture, deployment, phase plan, roadmap, audits |
| `scripts/` | local service control, deployment helpers, indexing, operations |
| `knowledge_graph/` | repo-level persisted knowledge events |
| `.run/` | local runtime and pid files |
| `backend/tests/` | focused backend tests |
| `tests/` | Playwright-style frontend/landing tests |

## 5. Architecture In One Picture

The practical architecture is:

1. The backend boots a single FastAPI process from `backend/app/main.py`.
2. Startup initializes storage, knowledge state, monitoring, broker state, streams, data pipeline, ML model bootstrapping, and optionally the agent runtime.
3. The backend exposes several API families:
   - direct trading and analytics endpoints
   - fund/orchestration endpoints
   - admin/research/blog endpoints
   - monitoring endpoints
   - knowledge endpoints
   - data-pipeline endpoints
   - backtest endpoints
4. The Vite frontend calls the backend through `frontend/src/api.js` and `frontend/src/api/adminAPI.js`.
5. The landing app is a separate Next.js surface that points users to the product frontend.
6. Persistent state lives in SQLite by default, with Postgres support in the storage layer.
7. The repo also maintains a separate development knowledge store under `knowledge_graph/`.

## 6. Canonical Source Of Truth By Concern

When you want to understand a concern, start here:

| Concern | Primary file(s) |
| --- | --- |
| Product mission and startup goal | `Vektor.md` |
| Development operating contract | `DevViktor.md` |
| Phasing and what matters now | `docs/VEKTOR_PHASED_EXECUTION_PLAN.md` |
| Runtime entrypoint | `backend/app/main.py` |
| App configuration | `backend/app/config.py` |
| Storage schema | `backend/app/storage/schema_sql.py` |
| DB access helpers | `backend/app/storage/db.py` |
| Paper broker | `backend/app/broker/paper.py` |
| Legacy signal engine | `backend/app/strategies/hybrid.py` |
| Legacy auto-trading loop | `backend/app/strategies/auto_trader.py` |
| Quant regime logic | `backend/app/quant/regime.py` |
| ML features | `backend/app/ml/features.py` |
| ML alpha model | `backend/app/ml/alpha_model.py` |
| Quant data pipeline | `backend/app/data_pipeline/service.py` |
| Fund API surface | `backend/app/fund/router.py` |
| Fund orchestration logic | `backend/app/fund/orchestrator.py` |
| Policy/risk gate for intents | `backend/app/fund/policy_gate.py` |
| Agent runtime | `backend/app/fund/agent_runtime.py` |
| Admin operator API | `backend/app/admin_research_routes.py` |
| Knowledge API | `backend/app/knowledge_routes.py` |
| Monitoring API | `backend/app/monitoring_routes.py` |
| Main React app routing | `frontend/src/App.jsx` |
| Main frontend API client | `frontend/src/api.js` |
| Admin frontend API client | `frontend/src/api/adminAPI.js` |
| Main operator page | `frontend/src/pages/Admin.jsx` |
| Public landing page | `landing-next/app/page.jsx` |

## 7. Backend Boot Sequence

The backend starts in `backend/app/main.py`.

### 7.1 What `main.py` wires together

It imports and includes:

- backtest router
- fund router
- admin router
- research router
- blog router
- monitoring router
- knowledge router
- data-pipeline router

It also installs:

- CORS middleware
- API key middleware
- startup and shutdown hooks
- REST endpoints
- websocket endpoints

### 7.2 Authentication model

The API-key middleware allows unauthenticated access to a small public set:

- `/health`
- `/ws`
- `/ws/agents`
- docs/openapi paths

Everything else requires `X-API-Key` outside dev mode.

### 7.3 What startup does

The startup hook is one of the most important functions in the repo. It:

1. configures agent-event websocket broadcast loop
2. starts a development log session
3. initializes the database
4. restores knowledge graph state
5. restores decision ledger, audit log, research memory, sentiment store, performance tracker, and task bus
6. backfills the in-process knowledge graph from persisted stores
7. restores broker state
8. starts market data stream loop
9. starts the quant data pipeline
10. optionally starts legacy auto-trading
11. optionally starts fund agent runtime
12. optionally starts performance tracker
13. ensures the ML alpha model is ready if possible

This means `main.py` is not a thin transport file. It is the runtime assembly point for the whole system.

## 8. Configuration Model

The canonical config lives in `backend/app/config.py` as a `pydantic-settings` `Settings` object.

### 8.1 Major config families

| Family | What it controls |
| --- | --- |
| Runtime identity | `APP_NAME`, `ENV`, `BROKER` |
| Safety and execution | `DETERMINISTIC_RUNTIME_MODE`, `LIVE_TRADING_ENABLED`, allowlists |
| Data pipeline | `DATA_PIPELINE_*` |
| Signal weights | `TECH_WEIGHT`, `FUND_WEIGHT`, `SENT_WEIGHT`, `ML_WEIGHT` |
| Agent runtime | `AGENT_RUNTIME_*` |
| Decision thresholds | `DECISION_GATE_*` |
| Capital defaults | `FUND_DEFAULT_*` |
| CEO approval rules | `CEO_APPROVAL_REQUIRED_*` |
| Auth and secrets | `SECRET_KEY`, `API_KEY` |
| Database | `DB_BACKEND`, `SQLITE_PATH`, `DATABASE_URL` |
| OpenClaw | `OPENCLAW_*` |
| Knowledge graph | `KNOWLEDGE_GRAPH_*`, `GRAPHIFY_*` |
| AI routing | `AI_ROLE_*` and provider-specific overrides |
| Monitoring / sentry / frontend origin | various app-level envs |

### 8.2 Important current defaults

The current checked-in defaults matter:

- `LIVE_TRADING_ENABLED` is false
- `BROKER` defaults to `paper`
- `DB_BACKEND` defaults to `sqlite`
- `DATA_PIPELINE_ENABLED` is true
- `AUTO_TRADING_ENABLED` is false
- `AGENT_RUNTIME_ENABLED` is false
- `REAL_DATA_STRICT_MODE` is false by default
- `DETERMINISTIC_RUNTIME_MODE` is true by default

Interpretation:

- the repo is still paper-first
- the legacy auto-trader does not run by default
- the new fund agent runtime does not run by default
- the system can operate in a deterministic guarded mode for development/admin use

## 9. Persistence Model

The storage layer is more important than it first looks because it combines:

- broker state
- fund workflow state
- knowledge events
- quant warehouse state

### 9.1 DB backend abstraction

`backend/app/storage/db.py` supports:

- SQLite default local storage
- Postgres when `DB_BACKEND=postgres` and `DATABASE_URL` is set

It does real compatibility work:

- schema creation
- placeholder conversion
- upsert conversion
- column backfill
- context-managed commit/rollback

### 9.2 Core operational tables

Defined in `backend/app/storage/schema_sql.py`:

| Table | Purpose |
| --- | --- |
| `orders` | paper order history |
| `positions` | current paper positions |
| `cash_snapshots` | broker cash history |
| `fund_task_history` | agent/task lifecycle history |
| `fund_decisions` | decision records |
| `fund_approval_requests` | pending and resolved approvals |
| `fund_ceo_digests` | generated CEO digest artifacts |
| `fund_post_trade_reviews` | post-trade review objects |
| `fund_decision_events` | decision event timeline |
| `fund_audit_events` | audit trail |
| `fund_research_reports` | stored research reports |
| `fund_sentiment_snapshots` | persisted sentiment snapshots |
| `fund_benchmark_baselines` | performance baselines |
| `fund_performance_snapshots` | equity and PnL snapshots |
| `fund_allocation_policies` | capital policy state |
| `fund_discovery_opportunities` | scanner opportunity records |
| `knowledge_events` | durable knowledge/event store |

### 9.3 Quant warehouse tables

Also defined in `schema_sql.py` and used through `backend/app/data_pipeline/warehouse.py`:

| Table | Purpose |
| --- | --- |
| `data_raw_events` | raw provider payload capture |
| `data_market_bars` | OHLCV bars |
| `data_market_prices` | price observations |
| `data_market_quotes` | quote/NBBO-like observations |
| `data_text_events` | news/text events |
| `data_fundamentals` | fundamentals snapshots |
| `data_quality_events` | quality checks and flags |
| `data_feature_vectors` | engineered features |
| `data_pipeline_runs` | pipeline run ledger |
| `data_provider_health` | provider state and freshness |
| `data_snapshots` | replayable data snapshots |

### 9.4 Storage philosophy

The repo's own phase plan says SQL should become the source of truth and the graph should be a projection. The current code already reflects that direction:

- business and quant objects are stored in SQL tables
- the knowledge graph is built from events and captures lineage
- the graph is not the only source of truth for stateful trading data

## 10. Broker And Execution Core

### 10.1 Shared broker instance

`backend/app/core/context.py` creates one shared `PaperBroker()` instance. That broker is reused across routes, the legacy auto-trader, and fund execution flows.

### 10.2 Paper broker behavior

`backend/app/broker/paper.py` owns:

- cash balance
- position map
- order history
- state restore from DB
- persist on change
- order fills and commission modeling

`submit_order()`:

- normalizes symbol, quantity, price
- computes filled price and gross notional
- charges commission
- updates cash and positions
- appends order history
- persists order and position state

The broker already supports metadata for:

- `asset_class`
- `instrument_type`
- `routing_mode`
- `underlier_symbol`
- `contract_multiplier`

That tells you the codebase is preparing for multi-asset semantics even though execution is still paper-first.

### 10.3 Execution adapter path

The higher-level fund workflow does not submit directly through a route. It passes through:

- fund orchestrator
- policy gate
- execution adapter
- paper broker

That is the separation between "legacy app orders" and "fund-governed execution".

## 11. Legacy Trading Layer

The legacy trading layer is still active and still matters because much of the repo's trading DNA lives there.

### 11.1 `backend/app/strategies/hybrid.py`

`hybrid_signal(symbol)` does:

1. load settings
2. fetch price history from `FEED.history()`
3. compute technical score
4. compute fundamental score
5. compute news sentiment score
6. optionally compute ML alpha score if model is ready
7. combine weighted scores
8. apply an ATR-based volatility filter
9. output action, score, subscores, weights, volatility, and metadata

It is the clearest "single-symbol signal contract" in the repo.

### 11.2 `backend/app/strategies/auto_trader.py`

`auto_trading_loop()` is the older continuous scanner/executor:

1. skips work if the data integrity guard is halted
2. refreshes positions and analytics
3. updates equity in the risk engine
4. scans the watchlist
5. calls `hybrid_signal()`
6. sizes with the risk engine
7. runs pre-trade checks
8. submits via paper broker
9. registers ATR stops
10. manages stop-loss and take-profit exits
11. broadcasts updates by websocket

This is the clearest end-to-end "bot loop" in the repository.

## 12. Risk Stack

There are two different risk concepts in Vektor:

1. Legacy trading risk in `backend/app/risk/engine.py`
2. Fund policy and intent gating in `backend/app/fund/policy_gate.py`

### 12.1 Legacy `RiskEngine`

`RiskEngine` includes:

- `VaRGuard`
- `DrawdownBreaker`
- `ATRStopManager`
- Kelly-based sizing
- concentration checks
- max open position checks
- stop and take-profit management

This is the risk layer used by the legacy auto-trader and direct order flow.

### 12.2 `PolicyGate`

`PolicyGate` is the more institutional gate. It evaluates execution intents against:

- approved flag presence
- broker mode and live-trading prohibition
- symbol and id completeness
- order notional limits
- max open positions
- symbol exposure
- sleeve budget remaining
- asset-class budget remaining
- cash reserve floor
- risk-off regime blocks
- thesis invalidation
- event-risk news thresholds
- correlated group exposure
- asset-class-specific constraints
- ML decision thresholds
- routing mode correctness

This is one of the strongest signals that Vektor is no longer just a bot. It has an explicit policy-control layer between decision and execution.

## 13. Market Data Stack

### 13.1 `backend/app/data/market_data.py`

This file is the main market data adapter. It provides:

- current price lookup
- history lookup
- cache behavior
- Alpaca REST usage
- Alpaca websocket streaming
- yfinance fallback for history
- test-mode synthetic prices and synthetic bars
- provider-event recording into the runtime guard

The important design choice is not just "get prices". It is "get prices while recording provenance, fallback usage, and degraded states".

### 13.2 `backend/app/data/fundamentals.py`

This file fetches basic fundamentals from Financial Modeling Prep.

If FMP is unavailable:

- it records a provider fallback event
- it can fail hard in strict mode
- otherwise it returns fallback defaults

### 13.3 `backend/app/data/news.py`

This file fetches company news from Finnhub, caches responses, and also routes through the data-integrity guard.

If Finnhub is not available:

- strict mode raises
- non-strict mode falls back to cached or sample data

### 13.4 Runtime guard

The data adapters are not isolated utility code. They are tied into `backend/app/fund/runtime_guard.py`, which is the repo's current safety mechanism for:

- provider mode tracking
- fallback detection
- strict real-data enforcement
- halt reasons

## 14. Quant Data Pipeline

The data pipeline is one of the most important additions in the repo.

### 14.1 Purpose

`backend/app/data_pipeline/service.py` defines `QuantDataPipeline`, which is a local-first pipeline with this explicit flow:

`ingest -> store -> process -> filter -> score -> categorize -> feature engineering`

### 14.2 What it does

The pipeline:

- chooses a configured symbol universe
- subscribes to streaming market events
- optionally starts Alpaca news stream
- runs a scheduled loop
- ingests price, bars, news, and fundamentals
- validates quality
- materializes feature vectors
- records provider health
- saves replayable snapshots

### 14.3 What gets stored

Through `backend/app/data_pipeline/warehouse.py`, the pipeline writes:

- raw provider payloads
- normalized prices
- normalized quotes
- bars
- fundamentals
- text events
- quality scores
- feature vectors
- run records
- provider health
- replay snapshots

### 14.4 Operational meaning

This is the repo's bridge from "app that trades" to "system that owns data lineage". It is the main reason the repo can support later institutional analysis without rewriting the entire data foundation.

## 15. Quant Package

The modern quant utilities are split under `backend/app/quant/`.

### 15.1 What the split means

The quant package is no longer a single `regime.py` monolith. Responsibilities are separated into:

| File | Responsibility |
| --- | --- |
| `common.py` | shared helpers |
| `types.py` | typed snapshots and models |
| `statistics.py` | indicator/statistical primitives |
| `technical.py` | technical signal helpers |
| `fundamental.py` | fundamental scoring helpers |
| `sentiment.py` | sentiment scoring helpers |
| `ml.py` | ML-oriented helpers |
| `probability.py` | probability-to-alpha mapping |
| `risk.py` | portfolio regime and risk helpers |
| `regime.py` | market-regime facade and compatibility layer |

### 15.2 `regime.py`

`infer_market_regime(df)` computes:

- ADX trend information
- ATR percent
- RSI and stochastic
- MACD histogram and acceleration
- Bollinger position and width
- volume ratio
- liquidity score
- momentum and z-score derived signals

It then classifies the market into regimes like:

- `TREND_UP`
- `TREND_DOWN`
- `BREAKOUT_UP`
- `BREAKOUT_DOWN`
- `MEAN_REVERT_UP`
- `MEAN_REVERT_DOWN`
- `HIGH_VOL`
- `RANGE`

This is much richer than a simple RSI threshold engine.

## 16. ML Stack

### 16.1 Feature engineering

`backend/app/ml/features.py` builds a flat numeric feature dictionary for LightGBM from OHLCV data.

Feature families include:

- returns
- distance from 52-week extremes
- SMA and EMA relationships
- ADX
- RSI
- stochastic
- MACD
- ROC
- Bollinger metrics
- ATR percent
- realized volatility
- OBV slope
- VWAP deviation
- volume z-score
- mean-reversion z-scores
- regime flags

### 16.2 Alpha model

`backend/app/ml/alpha_model.py`:

- trains on a watchlist of liquid names
- pulls 2 years of daily history via yfinance
- builds supervised samples using forward returns
- uses `TimeSeriesSplit` to reduce lookahead bias
- trains LightGBM
- reports AUC
- persists model and feature names when possible

This is not a huge institutional ML platform yet, but it is a genuine, structured ML subsystem rather than a placeholder.

## 17. Fund Operating System Layer

The `backend/app/fund/` package is where Vektor stops being just a trading bot.

### 17.1 Main idea

This package models the firm as a workflow system with:

- contracts
- task bus
- decision ledger
- audit log
- research memory
- approval center
- allocation policy
- execution adapters
- orchestrator
- agent runtime
- OpenClaw integration
- performance tracking
- knowledge graph

### 17.2 Contracts

`backend/app/fund/contracts.py` defines immutable pydantic models for:

- `AgentTask`
- `ResearchReport`
- `SentimentSnapshot`
- `TradeThesis`
- `ExecutionIntent`
- `RiskAssessment`
- `DecisionRecord`

This is the repo's typed business language.

### 17.3 Orchestrator

`backend/app/fund/orchestrator.py` is the center of the fund layer. It is large because it owns cross-cutting behavior:

- sleeve allocation
- allocation policy updates
- approval-request creation
- discovery opportunity recording
- research ingestion
- thesis creation
- sentiment ingestion
- decision execution
- audit timeline assembly
- OpenClaw ingest
- knowledge event access
- development-log ingest
- knowledge reset/rebuild
- sleeve budget tracking
- backfilling the knowledge projection

If `main.py` is runtime assembly, `orchestrator.py` is business-flow assembly.

### 17.4 Task bus

`backend/app/fund/task_bus.py` is the queue/history mechanism for role work and task state.

### 17.5 Decision ledger

`backend/app/fund/decision_ledger.py` stores:

- decisions
- status changes
- execution-adjacent events
- per-order and per-decision timelines

### 17.6 Audit log

`backend/app/fund/audit_log.py` is the durable control-plane event history.

### 17.7 Research memory

`backend/app/fund/research_memory.py` is the stored research artifact layer.

### 17.8 Approval center

`backend/app/fund/approval_center.py` handles approval-request lifecycle for things like:

- allocation changes
- trade execution
- editorial approval

### 17.9 Performance tracker

`backend/app/fund/performance_tracker.py` captures equity/PnL state into stored snapshots and CEO-facing summaries.

## 18. Agent Runtime

### 18.1 What it is

`backend/app/fund/agent_runtime.py` manages role-oriented background workers.

When started, it:

- marks every role as idle in the hierarchy
- publishes agent status events
- starts worker loops per role
- optionally starts autopilot
- optionally starts editorial loop
- optionally starts CEO digest loop

### 18.2 What this means architecturally

The agent runtime is real code, but it is controlled by config and does not define the whole product by itself. The repo currently supports:

- role-based workers
- task processing
- status broadcasting
- orchestration hooks

This is one of the main seams for future expansion into the multi-agent target design.

## 19. Knowledge And Development Memory

There are two different graph ideas in this repo:

1. The application's own `knowledge_graph/` runtime memory and event system.
2. The external `codebase-memory-mcp` graph used for developer code discovery.

Do not confuse them.

### 19.1 Application knowledge graph

`backend/app/fund/knowledge_graph.py` manages in-process persisted business and development events. It:

- normalizes namespaces
- ingests events
- captures upstream subsystem events
- persists to `knowledge_graph/events.jsonl`
- supports queries by run, agent, decision, order, namespace
- can rebuild projections
- can trigger graphify sync

### 19.2 Dev log plumbing

`backend/app/devlog.py` writes:

- `Dev_Logs.md`
- `knowledge_graph/events.jsonl`

That is why repo sessions are required to record both START and END.

### 19.3 API exposure

Knowledge can be queried through:

- `backend/app/fund/router.py`
- `backend/app/knowledge_routes.py`

This is how development events and fund lineage become inspectable.

## 20. API Surface

The backend exposes several distinct endpoint families.

### 20.1 Core app endpoints from `main.py`

```text
GET        /health
GET        /debug/websocket-stream
POST       /signals/generate
GET        /paper/positions
GET        /paper/orders
POST       /paper/order
GET        /news/{symbol}
GET        /analytics/summary
GET        /risk/status
GET        /market/prices
GET        /ml/status
WEBSOCKET  /ws
WEBSOCKET  /ws/agents
```

### 20.2 Fund endpoints from `fund/router.py`

This family covers:

- allocation and policy
- research, theses, decisions, sentiment
- task and worker status
- autopilot control
- CEO commands
- blocked trades and audit timelines
- OpenClaw ingest and command handling
- knowledge queries
- performance snapshots
- realtime stream websocket

### 20.3 Admin endpoints from `admin_research_routes.py`

This is a very large operator-facing API family. It covers:

- runtime badges and control
- pause/resume/recover flows
- inception reset and broker capital updates
- decision approval/rejection
- allocations and opportunities
- operator CRM
- audit and lineage
- CEO dashboards and digests
- approval queues
- editorial review
- market watch

This file is one of the highest-density backend files in the repo.

### 20.4 Data pipeline endpoints

`backend/app/data_pipeline/router.py` exposes:

- status
- manual run
- latest features per symbol
- storage estimation
- generic warehouse table inspection
- snapshot replay

### 20.5 Monitoring endpoints

`backend/app/monitoring_routes.py` exposes:

- system status
- agents and hierarchy
- active tasks
- pending decisions
- knowledge stats
- broker status
- detailed health

### 20.6 Knowledge endpoints

`backend/app/knowledge_routes.py` exposes:

- stats
- events
- lineage
- development log ingest
- reset
- projection rebuild

## 21. Frontend Stack

### 21.1 Main product app

The main product UI lives in `frontend/` and is a React 18 + Vite app.

Key libraries:

- `react`
- `react-router-dom`
- `recharts`
- `lucide-react`
- Tailwind CSS utilities plus custom CSS files

### 21.2 Route map

`frontend/src/App.jsx` defines:

- `/` -> `PublicPnlPage`
- `/legacy` -> `AlfredDashboard`
- `/admin` -> `Admin`
- `/research` -> `Research`
- `/blog` -> `Blog`
- `/audit/:decisionId` -> `AuditTrail`
- `/thesis/:thesisId` -> `ThesisDetail`

Interpretation:

- the default public product face is the public PnL page
- the older dashboard survives under `/legacy`
- the admin page is the main internal operator surface

### 21.3 API clients

There are two main frontend API layers:

| File | Purpose |
| --- | --- |
| `frontend/src/api.js` | lighter direct app API client for health, signals, positions, orders, websocket, analytics, basic fund status |
| `frontend/src/api/adminAPI.js` | large admin/research/blog API client |

### 21.4 Admin page

`frontend/src/pages/Admin.jsx` is a large control-room page. It imports:

- KPI cards
- decision queue
- risk gauges
- positions panels
- lineage views
- knowledge trace graph
- TradingView widget
- toast system

This page is effectively the operator OS surface for the current product.

### 21.5 Supporting component families

Important component areas:

| Area | Purpose |
| --- | --- |
| `components/admin/*` | admin dashboards and inspection widgets |
| `components/research/*` | research browsing and provenance views |
| `components/common/*` | connection, toast, skeleton, spark chart, nav |
| `components/*` | legacy/public trading dashboards and panels |

## 22. Public Landing And Blog Surfaces

### 22.1 `landing-next/`

This is the current public landing app. It is a separate Next.js app with:

- marketing copy
- "AI-native hedge fund operating system" positioning
- CTA to the product frontend
- animated public brand presentation

It is not the operator product. It is the public narrative surface.

### 22.2 `blog-next/`

This is a separate Next/Fumadocs-based app or template for blog/documentation content. It appears to be a distinct public/docs surface and not the same app as the Vite frontend.

## 23. Deployment And Operations

### 23.1 Local runtime management

The main repo-native service controller is `scripts/vektor-services.ps1`.

It manages:

- backend on `127.0.0.1:8000`
- ollama on `11434`
- OpenClaw gateway on `18789`

This is the right starting point for local service lifecycle in this repo.

### 23.2 Codebase indexing

`scripts/index-repo.ps1` refreshes the `codebase-memory-mcp` index. This is mandatory repo hygiene after a completed run.

### 23.3 Frontend deployment

There are Vercel configs for:

- `frontend/vercel.json`
- `landing-next/vercel.json`

The Vite app outputs `dist`, while the landing app builds as Next.js.

### 23.4 Backend deployment

The repo contains multiple deployment helpers and documents:

- `render.yaml`
- `scripts/aws/*`
- `scripts/oracle/*`
- `docs/DEPLOY_AWS_US_WEST_POSTGRES.md`
- `docs/DEPLOY_ORACLE_FREE_VM.md`
- `docs/DEPLOY_VERCEL_AZURE.md`

This tells you the backend has been treated as a deployable service across several hosting paths, not just a laptop app.

## 24. Testing Surface

Backend tests are focused and responsibility-oriented:

| Test file | Main concern |
| --- | --- |
| `test_signals.py` | signal generation |
| `test_quant_regime.py` | regime logic |
| `test_data_pipeline.py` | pipeline and freshness classification |
| `test_fund_pipeline.py` | research-to-execution flow |
| `test_fund_policy_gate.py` | trade policy enforcement |
| `test_fund_agent_runtime.py` | worker runtime and dev-log ingest |
| `test_fund_knowledge_graph.py` | application knowledge graph |
| `test_task_bus_persistence.py` | task history and deferred tasks |
| `test_admin_runtime_controls.py` | pause/resume/recovery/admin actions |
| `test_admin_status_badges.py` | operator health badge semantics |
| `test_performance_tracker.py` | snapshot/performance capture |
| `test_openclaw_*` | OpenClaw ingest and command flow |
| `tests/landing-page-links.spec.ts` | landing page verification |

The test layout matches the architecture: separate subsystems, not one giant end-to-end suite.

## 25. High-Density Files Worth Reading First

If you want maximum understanding quickly, read these first:

| File | Why it matters |
| --- | --- |
| `backend/app/main.py` | runtime assembly point |
| `backend/app/config.py` | real operating knobs |
| `backend/app/storage/schema_sql.py` | persistent data model |
| `backend/app/storage/db.py` | SQLite/Postgres behavior |
| `backend/app/strategies/hybrid.py` | legacy signal core |
| `backend/app/risk/engine.py` | legacy risk core |
| `backend/app/data_pipeline/service.py` | quant ingest engine |
| `backend/app/fund/contracts.py` | typed business objects |
| `backend/app/fund/orchestrator.py` | system brain for fund flows |
| `backend/app/fund/policy_gate.py` | institutional pre-trade gate |
| `backend/app/fund/agent_runtime.py` | role-based worker runtime |
| `backend/app/admin_research_routes.py` | operator control surface |
| `frontend/src/App.jsx` | frontend routing |
| `frontend/src/api/adminAPI.js` | what the admin actually calls |
| `frontend/src/pages/Admin.jsx` | main control-room UI |

## 26. File Atlas

### 26.1 Backend root files

| File | Meaning |
| --- | --- |
| `backend/app/__init__.py` | package root |
| `backend/app/main.py` | FastAPI entrypoint |
| `backend/app/config.py` | settings model |
| `backend/app/models.py` | request/response pydantic models for core app endpoints |
| `backend/app/analytics.py` | broker-derived analytics and metrics |
| `backend/app/admin_research_routes.py` | admin/research/blog operator API |
| `backend/app/monitoring.py` | runtime monitoring collector |
| `backend/app/monitoring_routes.py` | monitoring endpoints |
| `backend/app/knowledge_routes.py` | knowledge endpoints |
| `backend/app/devlog.py` | dev log and KB ingest helper |

### 26.2 Backend subpackages

| Package | Meaning |
| --- | --- |
| `backtest/` | backtesting engine and API |
| `broker/` | broker implementations, currently paper broker |
| `core/` | shared runtime objects like broker context |
| `data/` | market, news, and fundamental providers |
| `data_pipeline/` | warehouse and feature pipeline |
| `fund/` | orchestrator, contracts, approvals, tasks, knowledge, runtime |
| `indicators/` | technical indicators |
| `ml/` | feature engineering and alpha model |
| `quant/` | quant primitives and regime logic |
| `risk/` | legacy risk engine |
| `storage/` | schema and DB access |
| `strategies/` | legacy hybrid signal and auto trader |
| `utils/` | sentiment and helper utilities |
| `websocket/` | market and agent event streaming |

### 26.3 Frontend atlas

| File or area | Meaning |
| --- | --- |
| `frontend/src/main.jsx` | React bootstrap |
| `frontend/src/App.jsx` | route tree |
| `frontend/src/api.js` | basic API client |
| `frontend/src/api/adminAPI.js` | admin/research/blog API client |
| `frontend/src/pages/Admin.jsx` | internal operator console |
| `frontend/src/pages/PublicPnlPage.jsx` | public performance page |
| `frontend/src/pages/Research.jsx` | research surface |
| `frontend/src/pages/Blog.jsx` | blog surface in product app |
| `frontend/src/pages/AuditTrail.jsx` | order/decision lineage view |
| `frontend/src/pages/ThesisDetail.jsx` | thesis detail view |
| `frontend/src/pages/AlfredDashboard.jsx` | legacy dashboard |
| `frontend/src/components/admin/*` | admin widgets |
| `frontend/src/components/research/*` | research widgets |
| `frontend/src/components/common/*` | shared UI primitives |
| `frontend/src/styles/*` | page and component CSS |

### 26.4 Landing and blog atlas

| Area | Meaning |
| --- | --- |
| `landing-next/app/page.jsx` | public landing homepage |
| `landing-next/app/how-it-works/page.jsx` | public operating-model explanation |
| `landing-next/app/globals.css` | landing design system |
| `landing-next/components/*` | landing UI building blocks |
| `blog-next/*` | separate docs/blog app and content system |

### 26.5 Scripts atlas

| Script | Meaning |
| --- | --- |
| `scripts/vektor-services.ps1` | local runtime manager |
| `scripts/index-repo.ps1` | refresh codebase-memory index |
| `scripts/local-runtime-health.ps1` | local runtime checks |
| `scripts/aws/*` | AWS deployment, setup, migration helpers |
| `scripts/oracle/*` | Oracle VM deployment helpers |
| `scripts/deploy-*.ps1` | deployment entry scripts |

## 27. How To Read The Code In The Right Order

If you want the fastest path from zero understanding to real understanding, read in this order:

1. `Vektor.md`
2. `docs/VEKTOR_PHASED_EXECUTION_PLAN.md`
3. `backend/app/config.py`
4. `backend/app/storage/schema_sql.py`
5. `backend/app/storage/db.py`
6. `backend/app/main.py`
7. `backend/app/data/market_data.py`
8. `backend/app/strategies/hybrid.py`
9. `backend/app/risk/engine.py`
10. `backend/app/data_pipeline/service.py`
11. `backend/app/quant/regime.py`
12. `backend/app/ml/features.py`
13. `backend/app/ml/alpha_model.py`
14. `backend/app/fund/contracts.py`
15. `backend/app/fund/policy_gate.py`
16. `backend/app/fund/orchestrator.py`
17. `backend/app/fund/router.py`
18. `backend/app/admin_research_routes.py`
19. `frontend/src/App.jsx`
20. `frontend/src/api/adminAPI.js`
21. `frontend/src/pages/Admin.jsx`

That sequence takes you from mission, to config, to state, to runtime, to trading, to quant, to orchestration, to UI.

## 28. What Vektor Already Is, Technically

Vektor is already:

- a FastAPI backend
- a React operator application
- a Next.js landing app
- a paper broker and trading simulator
- a hybrid signal engine
- a quantitative data and feature pipeline
- a LightGBM alpha experiment path
- a sleeve-aware fund orchestration layer
- an approval and audit system
- a knowledge/event memory system
- a deployment-oriented project

## 29. What Vektor Is Not Yet

Despite the ambitious architecture, the repo is not yet:

- fully live-trading enabled
- fully institutional in external market-data entitlements
- fully complete in multi-agent production autonomy
- fully unified into one clean minimal app surface
- fully free of legacy and next-generation overlap

That overlap is normal. This repo is in transition from advanced bot to operating system.

## 30. Final Interpretation

The cleanest way to understand Vektor is this:

Vektor is a paper-first hedge-fund operating stack built on top of an earlier hybrid trading bot. The older bot still powers core mechanics like signals, broker flow, and risk sizing. The newer layers add data lineage, orchestration, policy, approvals, agent runtime, CEO/admin control, and knowledge persistence. The frontend is split between an operator product app and a public landing presence. The storage layer is already shaped like a real platform, not a toy app.

If you remember one sentence, remember this:

Vektor is not one thing; it is three systems being fused into one coherent product:

- a trading engine
- a data and quant platform
- a fund operating system

