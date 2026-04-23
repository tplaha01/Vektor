# ALPHA-003 ML Outcome Feedback and Threshold Tuning

Status: open
Priority: high
Depends on: `ALPHA-001`, `ALPHA-002`
Blocks: `ALPHA-006`

## Objective

Turn ML from a mostly static decision aid into an empirically tuned gate driven by realized paper-trading outcomes.

## Scope

- regression/classification/regime outputs
- realized trade outcome feedback
- threshold tuning data
- operator-visible model effectiveness
- approval/risk gating informed by actual outcomes

## Work Items

- [ ] Persist realized outcome summaries against prior discovery/decision scoring packets
- [ ] Build attribution between ML predictions and final trade results
- [ ] Add score/confidence bucket outcome analysis
- [ ] Add strategy-family and asset-class outcome analysis
- [ ] Expose threshold tuning evidence in admin
- [ ] Define guarded policy for adjusting thresholds from empirical results

## Acceptance Criteria

- ML gate thresholds are backed by observed outcomes, not only static defaults
- The system can show whether certain score/confidence bands are actually working
- Asset-class and strategy-family tuning is measurable and auditable

## Verification Commands

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/admin/ceo/digest
Invoke-RestMethod http://127.0.0.1:8000/api/admin/ceo/winners-losers
Invoke-RestMethod http://127.0.0.1:8000/api/admin/ceo/exposure
```

## Deliverables

- realized-outcome linkage for ML packets
- threshold tuning analysis surfaces
- documented threshold-adjustment policy
