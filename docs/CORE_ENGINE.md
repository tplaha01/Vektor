# Core Engine Plan: Deterministic Multi-Model Signal and Intent System

As of: 2026-05-23 (America/Phoenix)

## 1) Objective

Build a deterministic, institution-style signal engine that combines:

- technical analysis models,
- fundamental analysis models,
- sentiment analysis models,
- and a stacked intent model trained on model outputs plus realized outcomes.

The goal is higher precision and stronger trade intent quality, with strict reproducibility and measurable validation gates.

## 2) Non-Negotiable Design Rules

1. Deterministic orchestration: same inputs + same model versions + same config = same outputs.
2. Point-in-time correctness: no lookahead leakage in features, labels, or joins.
3. Domain specialization: technical/fundamental/sentiment models are trained on their own best-fit data.
4. Stacked learning: final intent is learned from domain outputs + regime/risk context + realized outcomes.
5. Risk-first deployment: shadow mode -> paper mode -> gated production path.
6. No single-model dependency: use champion/challenger and profile-based model routing.

## 3) Target Engine Architecture

```text
Data Ingest (market + fundamentals + news/social + events)
  -> Point-in-time Feature Store
  -> Domain Model Layer
     - Technical Model Pack
     - Fundamental Model Pack
     - Sentiment Model Pack
  -> Ensemble / Stacking Layer (Meta-Intent Model)
  -> Deterministic Policy Layer (risk + constraints + execution intent)
  -> Trader Action Payload (side, size, confidence, rationale, invalidation)
  -> Outcome Capture (realized pnl, slippage, drawdown, regret)
  -> Continuous Retraining + Calibration
```

## 4) Data Contracts (Training and Inference)

### 4.1 Technical Data

- OHLCV bars: multi-horizon (`1m`, `5m`, `15m`, `1h`, `1d`)
- Quote/Spread features: bid-ask spread, spread regime, liquidity proxies
- Volatility structure: ATR, realized vol, implied vol proxy if available
- Price action states: breakout, trend persistence, mean-reversion pressure
- Regime context: trend/downtrend/range/high-vol (already aligned with existing regime layer)

### 4.2 Fundamental Data

- Statement-derived metrics: growth, margins, leverage, cash flow quality
- Valuation factors: P/E, EV/EBITDA, FCF yield, sector-relative valuation
- Revision/event features: estimate revisions, earnings surprises, guidance delta
- Quality metadata: freshness, source confidence, missingness flags

### 4.3 Sentiment Data

- News wires + financial media + earnings calls/transcripts + social channels
- Entity-linked sentiment at ticker level (not global market-only sentiment)
- Source weighting and recency decay
- Event type extraction: product, litigation, regulation, macro exposure, analyst actions
- Crowd-vs-institution split proxy where possible

### 4.4 Labels and Outcome Targets

- Directional labels: `return_{1d,5d,20d} > threshold`
- Regression labels: cost-adjusted forward return
- Risk labels: adverse excursion, max drawdown risk, stop-hit probability
- Execution labels: expected slippage / fill quality (for intent confidence gating)

## 5) Model Stack (Per Domain)

## 5.1 Technical Model Pack

- Gradient boosting on tabular features (`LightGBM/CatBoost`) for fast/high-signal structure
- Deep time-series model (`TFT` or `TCN`) for multi-horizon sequence dynamics
- Regime classifier (`HMM` or sequence classifier) to route to best technical specialist
- Optional anomaly detector for regime breaks and unstable market states

Outputs:

- `p_up_horizon`, `expected_return`, `uncertainty`, `regime_probs`

## 5.2 Fundamental Model Pack

- Tabular ensemble (`CatBoost + ElasticNet`) for cross-sectional robustness
- Deep tabular model (e.g., FT-Transformer/TabNet) for nonlinear interactions
- Sector-conditional submodels to avoid one-size-fits-all bias

Outputs:

- `fundamental_alpha`, `valuation_gap_score`, `quality_score`, `uncertainty`

## 5.3 Sentiment Model Pack

- FinBERT-family classifier for finance-domain polarity
- Event-aware NLP head (event type + directional impact)
- Time-decayed source-weighted aggregation model
- Misinformation/noise suppression classifier for social feeds

Outputs:

- `sentiment_alpha`, `event_impact_score`, `crowd_institution_divergence`, `uncertainty`

## 5.4 RL / Policy Layer (Decision Optimization)

Use RL for policy optimization, not for raw prediction:

- Offline RL (`IQL`/`CQL`) on replayed historical state-action-outcome tuples
- State includes domain model outputs, risk state, costs, liquidity regime
- Reward function includes pnl, drawdown penalty, turnover cost, tail-risk penalty
- No unconstrained online exploration in live environments

Outputs:

- policy preference (`long/short/flat`), sizing suggestion, action-value confidence

## 6) Meta-Intent Model (Stacked Learner)

Train a final intent model on:

- technical/fundamental/sentiment model outputs,
- uncertainty vectors,
- regime/liquidity/risk context,
- and realized outcomes from prior decisions.

Recommended model family:

- calibrated gradient boosting or shallow neural stacker (stable first),
- then optional Mixture-of-Experts stacker for regime-based routing.

Primary outputs:

- `intent_score` in `[-1, 1]`,
- `intent_confidence` in `[0, 1]`,
- `expected_utility`,
- reason codes and feature attribution.

## 7) Deterministic Decision Policy

The policy layer must be deterministic and auditable:

1. Snapshot all required features at decision timestamp.
2. Run all domain models with pinned versions.
3. Run meta-intent model.
4. Apply hard risk gates (volatility, liquidity, exposure, session rules).
5. Produce explicit decision contract:
   - side, size, confidence, time horizon, stop/invalidations, rationale IDs.

If any mandatory component is stale/untrusted:

- degrade to safe mode (`hold` or reduced size),
- emit machine-readable rejection reason,
- record lineage event.

## 8) Training and Validation Protocol

### 8.1 Data Splitting

- Purged walk-forward CV with embargo windows
- Nested tuning windows for hyperparameter search
- Per-regime and per-asset-class stratification

### 8.2 Leakage Controls

- Point-in-time feature snapshots only
- Strict timestamp joins across market/fundamental/sentiment feeds
- Frozen source-latency assumptions for backtests

### 8.3 Optimization

- Bayesian optimization for key models
- Early stopping + calibration (Platt/Isotonic)
- Class imbalance controls (focal loss / weighted objectives when needed)

### 8.4 Evaluation Metrics

Prediction quality:

- AUC/PR-AUC, Brier score, calibration error, hit rate by confidence bucket

Trading quality:

- Sharpe/Sortino, max drawdown, turnover, hit rate, expectancy, slippage-adjusted return

Reliability:

- model drift, feature drift, confidence-to-outcome alignment, error budget burn rate

## 9) Configuration Strategy (Best Combo Profiles)

Use model profiles rather than one static blend:

- `accuracy_max`: highest expected utility, higher latency/cost
- `balanced`: strong utility with bounded cost/latency
- `latency_low`: fast intraday execution profile
- `risk_off`: conservative gating, high confidence threshold

Each profile pins:

- model subset,
- stacker version,
- thresholds,
- RL policy temperature,
- risk limits.

## 10) Repo Implementation Plan (Technical Work Breakdown)

## 10.1 New Modules

- `backend/app/core_engine/contracts.py`
- `backend/app/core_engine/feature_store.py`
- `backend/app/core_engine/domain_models/technical_pack.py`
- `backend/app/core_engine/domain_models/fundamental_pack.py`
- `backend/app/core_engine/domain_models/sentiment_pack.py`
- `backend/app/core_engine/stacking/meta_intent.py`
- `backend/app/core_engine/policy/deterministic_policy.py`
- `backend/app/core_engine/training/pipelines/*.py`
- `backend/app/core_engine/eval/*.py`
- `backend/app/core_engine/registry/model_registry.py`

## 10.2 Integration Touchpoints

- Extend existing signal path in `backend/app/strategies/`
- Use existing data pipeline in `backend/app/data_pipeline/`
- Reuse and evolve existing ML alpha and quant modules in `backend/app/ml/` and `backend/app/quant/`
- Expose status/introspection endpoints alongside current health surfaces

## 10.3 Storage and Lineage

- Persist model metadata: feature set hash, train window, metrics, calibration, drift stats
- Persist inference artifacts: per-domain outputs, intent output, policy gate decisions
- Persist realized outcomes for continuous retraining datasets

## 11) Execution Phases

## Phase 0: Contracts and Dataset Foundation

- finalize schemas for features, labels, outcomes, and decision artifacts
- implement point-in-time dataset builder
- implement deterministic replay harness

Exit gate:

- reproducible dataset generation and replay checks pass

## Phase 1: Domain Specialists

- train and validate technical/fundamental/sentiment packs
- add calibration and uncertainty estimation
- ship model cards and acceptance metrics per model

Exit gate:

- each domain pack beats current baseline with stable calibration

## Phase 2: Meta-Intent Stacker

- train stacked intent model on domain outputs + outcomes
- add explainability artifacts and confidence bucket tests

Exit gate:

- stacker improves utility and confidence reliability vs fixed-weight baseline

## Phase 3: RL Policy Optimization

- train offline RL policy on replayed decisions
- compare against deterministic heuristic policy under cost/risk constraints

Exit gate:

- RL policy outperforms baseline in risk-adjusted utility without tail risk regression

## Phase 4: Shadow, Paper, and Controlled Rollout

- shadow mode first (no execution)
- paper execution with strict gates
- promote only with sustained rolling-window performance

Exit gate:

- promotion checklist passes across prediction, execution, and risk metrics

## 12) Acceptance Criteria for "Strong Trading Intent"

The engine is considered production-capable only when:

1. Intent confidence is calibrated (high confidence consistently outperforms low confidence).
2. Risk-adjusted performance is positive after costs/slippage.
3. Drawdown and tail behavior stay within defined budget.
4. Drift alarms trigger deterministic fallback behavior.
5. Every decision has reproducible lineage from raw inputs to final intent.

## 13) Immediate Build Order (First Sprint)

1. Implement contracts + point-in-time dataset builder.
2. Ship technical model pack v1 with calibrated probabilities.
3. Ship fundamental and sentiment packs v1 with uncertainty outputs.
4. Train meta-intent v1 and integrate into existing deterministic signal flow.
5. Add outcome capture loop and start continuous retraining schedule.

## 14) Practical Note on Accuracy

Absolute accuracy is not guaranteed in live markets. The design target is:

- maximize expected utility under strict risk constraints,
- keep confidence calibrated,
- and ensure stable behavior under regime shifts.

This is how to produce a strong, executable trading intent engine in a deterministic and auditable way.
