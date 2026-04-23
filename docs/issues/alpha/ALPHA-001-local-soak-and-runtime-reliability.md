# ALPHA-001 Local Soak and Runtime Reliability

Status: in_progress
Priority: critical
Depends on: none
Blocks: `ALPHA-005`, `ALPHA-006`

## Objective

Prove that Vektor can operate locally for `48-72h` without queue drift, approval corruption, duplicate execution, provider thrash, or restart fragility.

## Scope

- backend runtime stability
- task queue integrity
- provider throttle/defer behavior
- approval workflow stability
- restart/recovery behavior
- performance tracker continuity
- admin/health endpoint consistency

## Work Items

- [ ] Run a `48h` soak with `scripts/run-local-soak.ps1`
- [ ] Capture runtime snapshots at fixed intervals
- [ ] Record provider throttle, cooldown, failover, and defer patterns
- [ ] Record queue depth, pending approvals, and stalled-task anomalies
- [ ] Force at least one controlled backend restart during the soak
- [ ] Verify no duplicate trades or duplicate decision records appear after restart
- [ ] Verify strict real-data halt behavior still works under provider/data failure
- [ ] Summarize failures, regressions, and fixes in `Dev_Logs.md`

## Acceptance Criteria

- No unbounded queue growth
- No duplicate execution for the same decision
- No orphaned pending approvals after restart
- Deferred tasks recover or fail explicitly with traceable reasons
- Health, admin, and performance endpoints remain usable through the run
- Restart recovery is clean and does not corrupt task or approval state

## Verification Commands

```powershell
.\scripts\local-runtime-health.ps1
.\scripts\run-local-soak.ps1 -DurationHours 48 -IntervalSeconds 30
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/admin/ceo/approvals/pending
Invoke-RestMethod http://127.0.0.1:8000/fund/agents/tasks/history?limit=100
```

## Deliverables

- soak output directory under `.run/soak/...`
- written soak summary
- any bug fixes required for stability

## Active Execution Evidence

- Active soak run:
  - output directory: `C:\Users\tplah\OneDrive\Desktop\ASU\Projects\TradingBot\.run\soak\20260423-035739`
  - pid file: `C:\Users\tplah\OneDrive\Desktop\ASU\Projects\TradingBot\.run\alpha-soak.pid`
  - stdout log: `C:\Users\tplah\OneDrive\Desktop\ASU\Projects\TradingBot\.run\alpha-soak.stdout.log`
  - stderr log: `C:\Users\tplah\OneDrive\Desktop\ASU\Projects\TradingBot\.run\alpha-soak.stderr.log`
- Autopilot cycle queued to seed runtime activity:
  - `run_id = run-autopilot-f1080c540308`
