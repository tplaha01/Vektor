# Vektor Local-First Operations Runbook

This runbook is the operator baseline for building an auditable paper-trading track record locally before cloud scale-out.

## Objective

Run Vektor locally with:

- durable event, audit, decision, research, sentiment, and performance storage
- strict real-data controls
- repeatable service startup
- exportable track-record artifacts
- local backups for month-scale continuity

## Required local services

- Backend: `127.0.0.1:8000`
- Frontend admin: `127.0.0.1:9000`
- OpenClaw gateway: `127.0.0.1:18789`
- Ollama: `127.0.0.1:11434`

## Service control

Status:

```powershell
.\scripts\vektor-services.ps1 status
```

Health:

```powershell
.\scripts\vektor-services.ps1 health
```

Start:

```powershell
.\scripts\vektor-services.ps1 up
```

Restart:

```powershell
.\scripts\vektor-services.ps1 restart
```

## Track-record capture

Vektor now persists `fund_performance_snapshots` plus benchmark baselines in SQLite.

Stored per snapshot:

- equity
- cash
- market value
- realized and unrealized PnL
- total PnL
- closed trades, wins, losses, win rate
- max drawdown from realized trade curve
- open positions snapshot
- benchmark returns from inception baseline

Automatic behavior:

- startup snapshot on backend boot
- intraday snapshots on configured interval
- daily snapshot when a new US trading date is observed

Config in `backend/.env`:

```env
PERFORMANCE_TRACKER_ENABLED=true
PERFORMANCE_TRACKER_INTERVAL_SECONDS=900
PERFORMANCE_TRACKER_BENCHMARKS=SPY,QQQ,GLD,TLT
```

## Performance APIs

Summary:

```text
GET /fund/performance/summary
```

Snapshots:

```text
GET /fund/performance/snapshots?limit=500
```

Manual capture:

```text
POST /fund/performance/capture
{
  "snapshot_kind": "manual",
  "reason": "operator_checkpoint"
}
```

Reset performance history:

```text
POST /fund/performance/reset
```

Use reset only when you intentionally restart the track record.

## Clean inception workflow

If you want the next 6-9 months to begin from a true clean paper ledger instead of inheriting old paper positions, orders, and performance snapshots:

```text
POST /api/admin/system/inception/reset
{
  "starting_cash_usd": 100000,
  "reason": "clean_inception_reset"
}
```

This single endpoint:

- clears persisted paper orders
- clears persisted paper positions
- resets cash history to the provided starting cash
- resets performance snapshots and benchmark baselines
- resets in-memory risk breaker state
- captures a fresh inception snapshot immediately

## Export track record

Generate JSON and CSV artifacts:

```powershell
.\scripts\export-track-record.ps1
```

Output:

- `performance-summary.json`
- `performance-snapshots.json`
- `performance-snapshots.csv`
- `pending-decisions.json`
- `blocked-trades.json`

Default destination:

- `.artifacts/track-record/<timestamp>/`

## Local backups

Create a local backup bundle:

```powershell
.\scripts\local-backup.ps1
```

Included:

- `backend/trading_bot.db`
- `backend/trading_bot.log`
- `Dev_Logs.md`
- `knowledge_graph/`
- exported track-record artifacts

Default destination:

- `.backups/<timestamp>/`

## Nightly exports and backup rotation

Run the full nightly maintenance job manually:

```powershell
.\scripts\nightly-maintenance.ps1
```

What it does:

- exports the latest track record into `.artifacts/track-record/nightly/<timestamp>/`
- creates a local backup bundle into `.backups/nightly/<timestamp>/`
- prunes old track-record directories older than 30 days
- prunes old backup directories older than 14 days

Register a daily Windows scheduled task:

```powershell
.\scripts\register-nightly-maintenance.ps1
```

Default schedule:

- daily at `11:55 PM` local machine time

## Daily operator routine

1. Verify service health.
2. Verify `Data Source = Provider` and `Execution Mode = Paper Only`.
3. Export track record once per day.
4. Create a local backup once per day.
5. Review blocked trades and audit timeline.
6. Record major changes in `Dev_Logs.md`.

## Weekly operator routine

1. Review track-record summary:
   - total return
   - alpha vs primary benchmark
   - max drawdown
   - Sharpe ratio
2. Review strategy drift and blocked-trade causes.
3. Archive the latest backup bundle externally.
4. Review model/runtime failures and stale dependencies.

## What this is and is not

This is sufficient to build an auditable local paper-trading record.

This is not yet a fund-admin or regulatory system. It is an operator-grade evidence layer for:

- hypothesis validation
- performance tracking
- YC / advisor / cofounder diligence
- future migration to a persistent cloud backend
