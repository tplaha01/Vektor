# ALPHA-004 Risk Framework Completion

Status: in_progress
Priority: high
Depends on: `ALPHA-001`, `ALPHA-002`, `ALPHA-003`
Blocks: `ALPHA-006`

## Objective

Make risk a true gatekeeper across the full fund workflow rather than a mainly pre-trade blocker.

## Scope

- asset-class-specific limits
- correlated exposure controls
- event-risk / risk-off controls
- thesis lifecycle:
  - valid
  - degraded
  - broken
- stricter pre-trade and post-trade review hooks

## Work Items

- [ ] Formalize thesis state transitions and persistence
- [ ] Add post-trade review events tied to thesis state changes
  - 2026-04-23: added persisted `fund_post_trade_reviews` storage and CEO/OpenClaw review snapshot generation for open positions
- [ ] Tighten concentration and correlated-group policies where soak evidence shows weakness
- [ ] Add event-risk escalation behavior for exceptional news conditions
- [ ] Expose thesis state and post-trade review in admin/OpenClaw
  - 2026-04-23: added CEO endpoints and OpenClaw command routing for thesis status / post-trade review
- [ ] Ensure no execution path bypasses the updated risk lifecycle

## Acceptance Criteria

- Risk can invalidate a trade thesis after entry
- Post-trade review is part of the system, not an afterthought
- Correlated exposure and event-risk behaviors are explainable and visible
- Admin can show the current thesis/risk state of open positions

## Verification Commands

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/admin/ceo/risk-alerts
Invoke-RestMethod http://127.0.0.1:8000/api/admin/ceo/positions
```

## Deliverables

- thesis lifecycle model
- post-trade risk review hooks
- richer risk visibility and enforcement
