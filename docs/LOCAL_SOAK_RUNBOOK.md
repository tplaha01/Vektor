# Local Soak Runbook

This is the Phase Alpha reliability gate before any VM deployment.

## Goal

Run Vektor locally for `48-72` hours and capture enough runtime evidence to answer:

- Does the backend stay up?
- Do scheduled digest loops continue running?
- Do deferred tasks recover instead of stalling?
- Do provider cooldowns budget correctly under load?
- Do approvals, signal packs, and task queues remain coherent over time?

## Quick commands

One-shot runtime check:

```powershell
.\scripts\local-runtime-health.ps1
```

Structured JSON output:

```powershell
.\scripts\local-runtime-health.ps1 -AsJson
```

24-hour soak:

```powershell
.\scripts\run-local-soak.ps1 -DurationHours 24 -IntervalSeconds 30
```

48-hour soak:

```powershell
.\scripts\run-local-soak.ps1 -DurationHours 48 -IntervalSeconds 30
```

## Output

Each soak run writes to:

```text
.run/soak/<timestamp>/
```

Files:

- `snapshots.jsonl`
  - one JSON document per interval
- `events.log`
  - human-readable notable events
- `summary.json`
  - roll-up summary for the run

## What is captured

Every snapshot records:

- backend health
- orchestration/data/execution/LLM health badges
- halt state
- active task count
- signal pack count
- pending decision count
- pending approval count
- CEO digest loop state and last digest id
- provider budget/cooldown state
- frontend/backend/blog process memory

## Minimum Alpha exit criteria for local soak

Do not move to VM hosting until a soak run shows:

- `probe_failures = 0`
- `halt_observations = 0` unless you intentionally forced a halt test
- digest loop stays running
- no persistent growth pattern in backend RSS that suggests leakage
- no repeated provider-throttle storms that prevent recovery
- pending approvals and signal packs do not drift upward without clearing

## Interpreting the summary

Focus on:

- `probe_failures`
- `halt_observations`
- `provider_throttle_events`
- `max_active_tasks`
- `max_pending_approvals`
- `memory_peaks_mb.backend`

High throttle counts are not automatically fatal on free-tier providers, but they are a problem if:

- deferred tasks never clear
- signal packs accumulate without dispatching
- CEO digests stop recording

## Recommended operating pattern during soak

1. Start backend, admin frontend, and blog.
2. Confirm:
   - `http://127.0.0.1:8000/health`
   - `http://127.0.0.1:9000/admin`
   - `http://127.0.0.1:3001`
3. Trigger a few real analyst/scout cycles.
4. Leave Vektor running normally.
5. Review `summary.json` after the run.

## If the soak fails

Do not deploy to a VM.

Use the last run directory to inspect:

- whether the failure was provider quota pressure
- whether the runtime halted
- whether process memory drifted
- whether approvals or queues stopped progressing
