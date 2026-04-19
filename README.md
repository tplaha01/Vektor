# Vektor (Paper-First AI-Native Hedge Fund OS)

Vektor is evolving from a single-loop trading bot into a multi-agent hedge fund operating system.

Current architecture keeps migration-safe compatibility:

- `backend` (FastAPI): orchestration, risk gates, audit logs, and paper execution.
- `frontend` (React/Vite): operator product UI (dashboard, monitoring, controls).
- `landing-next` (Next.js App Router): SSR public landing site for SEO/indexing.

Live trading remains disabled.

## System Architecture

```text
Research + Sentiment Agents
  -> Research Reports (source-backed)
  -> Thesis / Decision Contracts (immutable IDs)
  -> Risk Policy Gate
  -> Execution Intent (paper broker)
  -> Audit Timeline + Observability
```

## Run Locally

Run each service in its own terminal.

### One-command local shell screen (Windows PowerShell)

Use the service controller script:

```powershell
# Start required app services (backend + frontend)
.\scripts\vektor-shell.ps1 up

# Start with optional SSR landing/blog services too
.\scripts\vektor-shell.ps1 up -IncludeLanding -IncludeBlog

# Show current service state
.\scripts\vektor-shell.ps1 status

# Tail logs for one service
.\scripts\vektor-shell.ps1 logs -Service backend -Follow

# Stop all Vektor local services
.\scripts\vektor-shell.ps1 down
```

### 1) Backend API

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Backend URL: `http://localhost:8000`

### 2) Product App (React)

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend URL: `http://localhost:9000`

### 3) Landing Site (Next SSR)

```bash
cd landing-next
npm install
copy .env.example .env
npm run dev
```

Landing URL: `http://localhost:3000`

## SEO Split (what you requested)

- Public/marketing traffic should go to `landing-next` (SSR, robots, sitemap).
- Logged-in/product workflows stay in `frontend` until full Next migration is planned.
- Landing links users into the product app URL configured via `NEXT_PUBLIC_PRODUCT_APP_URL`.

## Key Backend Endpoints (phase-1 fund OS)

- `GET /fund/agents/tasks/active`
- `GET /fund/decisions/pending`
- `GET /fund/trades/blocked`
- `GET /fund/audit/orders/{order_id}/timeline`
- `GET /fund/agents/autopilot/status`
- `POST /fund/agents/autopilot/kick`
- `GET /fund/sleeves/budgets`
- `GET /fund/openclaw/health`
- `POST /fund/openclaw/ingest` (token required)
- `POST /fund/openclaw/commands` (token required)
- `GET /fund/openclaw/commands/health`
- `GET /fund/openclaw/commands/rejections`
- `GET /fund/knowledge/events`
- `GET /fund/knowledge/lineage`
- `GET /fund/knowledge/stats`
- `POST /fund/ceo/commands`
- `GET /fund/agents/workers/status`

## Environment Notes

`backend/.env` must include valid API keys and fund settings. You already replaced placeholders; keep these values private.

For `landing-next/.env`:

- `NEXT_PUBLIC_SITE_URL` (for metadata/sitemap canonical URL)
- `NEXT_PUBLIC_PRODUCT_APP_URL` (where "Open Product App" points)

For `backend/.env` knowledge graph:

- `KNOWLEDGE_GRAPH_ENABLED=true`
- `KNOWLEDGE_GRAPH_DIR=knowledge_graph`
- `KNOWLEDGE_GRAPH_PERSIST=true`
- `GRAPHIFY_SYNC_ENABLED=false` (turn on only after validating Graphify command)
- `GRAPHIFY_UPDATE_COMMAND=py -3 -m graphify update .`

For autonomous worker runtime:

- `AUTO_TRADING_ENABLED=false` (disable legacy single-loop trader)
- `AGENT_RUNTIME_ENABLED=true` (enable role-based worker runtime)
- `AGENT_RUNTIME_POLL_INTERVAL_SECONDS=1.5`
- `AGENT_RUNTIME_AUTOPILOT_ENABLED=true` (continuous task seeding loop)
- `AGENT_RUNTIME_AUTOPILOT_INTERVAL_SECONDS=120`
- `AGENT_RUNTIME_AUTOPILOT_SYMBOLS=AAPL,MSFT,NVDA,SPY`
- `AGENT_RUNTIME_AUTOPILOT_DEFAULT_SIDE=buy`
- `AGENT_RUNTIME_AUTOPILOT_DEFAULT_QUANTITY=1`
- `AGENT_RUNTIME_AUTOPILOT_SLEEVE=tactical`

For OpenClaw command adapter (Discord -> CEO command routing):

- `OPENCLAW_COMMANDS_ENABLED=true`
- `OPENCLAW_COMMAND_TOKEN=<optional; defaults to OPENCLAW_INGEST_TOKEN>`
- `OPENCLAW_COMMAND_CHANNEL_ALLOWLIST=vektor-ceo` (channel IDs or names)
- `OPENCLAW_COMMAND_SENDER_ALLOWLIST=<optional sender IDs/names>`
- `OPENCLAW_COMMAND_ROLE_ALLOWLIST=researcher,sentiment_researcher,fund_manager,trader,risk_auditor`
- `OPENCLAW_COMMAND_CHANNEL_ROLE_POLICIES=vektor-ceo=researcher,sentiment_researcher,fund_manager,trader,risk_auditor`

## Repo Structure

```text
backend/
frontend/
landing-next/
agents/
docs/
subagents/
```

## Next Migration Path

1. Keep running this hybrid setup (Next landing + React product app).
2. Incrementally move product surfaces from `frontend` into Next routes.
3. Keep backend contracts stable during UI migration.

## Deploy (Vercel + Azure)

- Frontend (`frontend`) -> Vercel
- Backend (`backend`) -> Azure App Service (Linux/Python)

See full runbook:

- `docs/DEPLOY_VERCEL_AZURE.md`

Quick start:

```powershell
vercel login
az login --use-device-code
.\scripts\deploy-all.ps1 -AzureAppName "<globally-unique-app-name>"
```

## Deploy (Vercel + Oracle Free VM)

- Frontend (`frontend` / `landing-next`) -> Vercel
- Backend (`backend`) -> Oracle Always Free VM (systemd, daily backups)

Runbook:

- `docs/DEPLOY_ORACLE_FREE_VM.md`

Oracle setup scripts:

- `scripts/oracle/setup_oracle_backend.sh`
- `scripts/oracle/backup_backend.sh`

## Startup Canonical Spec

- Repository source-of-truth startup document: `Vektor.md`
- All agent/model environments should read `Vektor.md` before planning or implementation.
