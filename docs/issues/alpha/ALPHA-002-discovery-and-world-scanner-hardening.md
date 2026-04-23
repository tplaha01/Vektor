# ALPHA-002 Discovery and World Scanner Hardening

Status: in_progress
Priority: high
Depends on: `ALPHA-001`
Blocks: `ALPHA-006`

## Objective

Make Vektor's discovery layer credible as a real source of trade candidates rather than a thin symbol scorer.

## Scope

- dedicated scanner behavior
- candidate discovery, scoring, pruning, and wave queueing
- world/event/news-driven market mover identification
- explicit no-trade / sit-in-cash path
- operator visibility into why names were advanced or rejected

## Work Items

- [ ] Formalize scanner roles and outputs
- [ ] Expand candidate ranking inputs:
  - catalyst significance
  - liquidity
  - volatility
  - news intensity
  - regime alignment
- [ ] Add explicit prune reasons for rejected candidates
- [ ] Add explicit `no_trade` / `cash_hold` outcome when nothing clears threshold
- [ ] Expose ranked candidate list and prune reasons in admin/OpenClaw
  - 2026-04-23: discovery statuses now persist as `selected`, `qualified`, `pruned_threshold`, `pruned_capacity`, and `no_trade`
  - 2026-04-23: admin ML scoring panel now shows selected/not-selected state, prune reason, and the latest cash-hold directive
  - 2026-04-23: OpenClaw `discovery status` now reports status counts, selected symbols, pruned symbols, and the latest no-trade/cash-hold event
- [ ] Verify wave scheduling reflects ranked priority and backlog state

## Acceptance Criteria

- Discovery output is explainable for both selected and rejected names
- The system can explicitly decide not to trade
- Ranked candidates are not just a static watchlist permutation
- Admin can show what was discovered, what was pruned, and why

## Verification Commands

```powershell
Invoke-RestMethod http://127.0.0.1:8000/fund/discovery/opportunities?limit=25
Invoke-RestMethod http://127.0.0.1:8000/api/admin/discovery/opportunities?limit=25
Invoke-RestMethod http://127.0.0.1:8000/fund/agents/workers/status
```

## Deliverables

- improved discovery scoring logic
- prune/no-trade semantics
- admin-visible ranked discovery pipeline
