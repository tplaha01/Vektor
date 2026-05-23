# Core Engine Plan: Deterministic Quant Decision System

As of: 2026-05-23 (America/Phoenix)

## 1) Objective

Vektor trade decisions must come from deterministic quantitative models, not LLM reasoning.

Signal generation must be produced by:

- supervised ML models,
- deep learning sequence models,
- offline reinforcement learning policy models,
- stochastic simulation and risk-utility optimization,
- deterministic policy gates.

The engine objective is not "AI-native narration"; it is reproducible risk-adjusted return with strict auditability.

## 2) Hard Constraints (Must Hold)

1. No LLM in signal path: LLMs may assist research/docs only, never directional score, confidence, side, size, or policy gating.
2. Deterministic inference: same snapshot + same model versions + same config must produce identical output.
3. Point-in-time data integrity: zero lookahead leakage in joins, features, labels, and regime tagging.
4. Cost-aware optimization: all model selection and policy scoring are slippage/fees/impact adjusted.
5. Tail-risk discipline: any candidate trade must pass drawdown, VaR/CVaR, and scenario stress gates.
6. No indicator-only or polarity-only decisioning: handcrafted indicators and naive sentiment polarity are diagnostics only.

## 3) Legacy Paths Explicitly Removed

The following are prohibited for final trade intent generation:

- LLM-generated buy/sell/hold or confidence outputs.
- Prompt-assembled "analyst votes" as a direct decision mechanism.
- Single-source polarity sentiment (for example pure VADER polarity average) as a trade signal.
- Low-level indicator threshold logic as primary alpha decisioning.

Allowed usage of legacy artifacts:

- observability diagnostics,
- feature inputs into learned models,
- explanatory overlays for operator UI.

## 4) Target End-to-End Architecture

```text
Data Ingest (market microstructure + fundamentals + event/text + macro)
  -> Point-in-time Feature Store
  -> Learned Domain Model Layer
     - Market State & Return Forecast Models
     - Fundamental Cross-Section Models
     - Event Impact NLP Models
  -> Meta-Model / Mixture-of-Experts Router
  -> Offline RL Policy Layer (action optimization under constraints)
  -> Monte Carlo / Scenario Engine (distribution and tail checks)
  -> Deterministic Risk Policy Gate
  -> Intent Contract (side, size, horizon, confidence, invalidation)
  -> Outcome Capture + Replay Store
  -> Continuous Retraining + Champion/Challenger Rotation
```

## 5) Data Specification (Training + Inference)

## 5.1 Market and Microstructure Inputs

- Multi-horizon bars and returns (`1m`, `5m`, `15m`, `1h`, `1d`)
- Realized volatility surface, volatility-of-volatility
- Spread, depth, trade imbalance, volume profile, liquidity stress proxies
- Regime state inputs (trend, range, transition, volatility shock) as model features, not fixed rules
- Corporate actions and calendar events aligned point-in-time

## 5.2 Fundamental Inputs

- Financial statement tensors (growth, quality, leverage, profitability, valuation)
- Revision flows (estimates, guidance, analyst target drift)
- Sector and factor context (cross-sectional normalization)
- Freshness and confidence metadata per source

## 5.3 Event/Text Inputs (Not Polarity-Only)

- Entity-linked event extraction from news/transcripts/filings
- Event taxonomy (earnings miss/beat, regulation, litigation, supply shock, guidance)
- Event severity and horizon impact forecasts
- Contradiction/noise classifier for source quality control

Note: sentiment polarity may exist as a minor feature but cannot be the terminal signal component.

## 5.4 Labels and Targets

- Multi-horizon cost-adjusted forward return labels
- Classification targets for directional edge with uncertainty bins
- Risk targets: adverse excursion, stop-hit probability, tail-loss likelihood
- Execution targets: expected slippage and fill-quality estimates

## 6) Model Families (Required Quant Stack)

## 6.1 Supervised ML Layer

- Gradient boosting ensembles (`LightGBM`, `CatBoost`, `XGBoost`) for tabular robustness
- Regularized linear baselines (`ElasticNet`, logistic with calibration) as controls
- Cross-sectional factor and residual models for stable baseline alpha

## 6.2 Deep Learning Layer

- Temporal models (`TFT`, `TCN`, Transformer encoder variants) for sequence structure
- Deep tabular architectures (FT-Transformer/TabNet) for nonlinear feature interactions
- Optional graph/message-passing extensions for cross-asset dependency structure

## 6.3 Offline RL Policy Layer

Use RL only for constrained action optimization over model-derived state:

- algorithms: `IQL`, `CQL`, or equivalent conservative offline RL
- state: domain model outputs + uncertainty + risk + liquidity + costs
- action: {flat, long, short} and discrete/continuous sizing buckets
- reward: return - transaction_cost - impact_penalty - drawdown_penalty - tail_penalty

No unconstrained online exploration is allowed in paper/live runtime.

## 6.4 Stochastic Simulation Layer (Monte Carlo)

- Regime-conditioned Monte Carlo path simulation for forward PnL distribution
- Jump/volatility shock scenarios and bootstrap stress replay
- VaR/CVaR and probability-of-ruin constraints per candidate intent
- Reject or downsize intents that fail scenario thresholds

## 7) Meta-Decision and Routing

Final intent is generated by deterministic meta-model routing, not heuristic averaging.

Recommended structure:

- mixture-of-experts or calibrated stacked learner,
- uncertainty-aware weighting,
- regime-conditioned model selection,
- hard confidence monotonicity and calibration checks.

Required outputs:

- `intent_score` in `[-1, 1]`
- `intent_confidence` in `[0, 1]`
- `expected_return_net_cost`
- `expected_tail_risk`
- `action_utility`
- deterministic `reason_codes`

## 8) Deterministic Policy Gate

After meta-decision, enforce deterministic policy:

1. exposure and concentration limits,
2. liquidity and spread constraints,
3. volatility and drawdown breakers,
4. VaR/CVaR/tail-risk thresholds,
5. data freshness and model-health checks.

If any gate fails:

- produce `hold` or reduced-size action deterministically,
- emit explicit machine-readable rejection reasons,
- persist full lineage.

## 9) Validation Standard (Profitability-Focused)

## 9.1 Backtest Protocol

- purged walk-forward cross-validation with embargo windows
- strict point-in-time replay
- transaction cost, spread, and slippage modeling
- capacity and turnover constraints

## 9.2 Statistical Reliability

- probability of backtest overfitting controls
- bootstrap confidence intervals
- regime-by-regime and asset-class-by-asset-class performance stability
- calibration error and confidence bucket monotonicity

## 9.3 Minimum Deployment Gates

- positive net expectancy after costs
- controlled max drawdown under defined budget
- stable Sharpe/Sortino across rolling windows
- no severe tail-risk regression in stress scenarios

## 10) Repo Implementation Blueprint

## 10.1 Core Modules

- `backend/app/core_engine/contracts.py`
- `backend/app/core_engine/feature_store.py`
- `backend/app/core_engine/domain_models/market_pack.py` (new)
- `backend/app/core_engine/domain_models/fundamental_pack.py`
- `backend/app/core_engine/domain_models/event_nlp_pack.py` (new)
- `backend/app/core_engine/stacking/meta_intent.py`
- `backend/app/core_engine/policy/deterministic_policy.py`
- `backend/app/core_engine/simulation/monte_carlo.py` (new)
- `backend/app/core_engine/rl/offline_policy.py` (new)
- `backend/app/core_engine/training/pipelines/*.py`
- `backend/app/core_engine/eval/*.py`
- `backend/app/core_engine/registry/model_registry.py`

## 10.2 Integration Points

- signal endpoint remains `POST /signals/generate` with profile routing
- policy and runtime guards remain deterministic and machine-checkable
- admin UI shows model health, calibration, and risk gate outcomes (not LLM rationale)

## 10.3 Lineage and Audit

Persist for every decision:

- feature snapshot hash,
- model versions and profile,
- meta-decision output,
- RL policy output,
- Monte Carlo risk summary,
- policy gate verdict,
- emitted intent and realized outcome.

## 11) Migration Plan from Current State

## Phase A: Remove Legacy Signal Dependencies

- disable any LLM-derived signal contribution in runtime paths
- mark indicator thresholds and polarity-only outputs as non-decision diagnostics
- enforce unit tests that fail if LLM fields are consumed by signal generation

## Phase B: Quant Model Upgrade

- upgrade market/fundamental/event packs to learned model families
- introduce calibrated uncertainty outputs in all packs
- add champion/challenger registry controls

## Phase C: RL + Monte Carlo Hardening

- add offline RL policy inference
- add Monte Carlo risk distribution checks pre-intent
- add deterministic gating on tail metrics

## Phase D: Controlled Rollout

- shadow mode -> paper mode -> promote only on rolling net performance and risk stability

## 12) Definition of Done for This Core Engine

The core engine is complete only when:

1. No LLM signal logic is referenced in decision generation code paths.
2. Final decisions are produced by deterministic ML/DL/RL + scenario risk stack.
3. Indicator-only and polarity-only methods are non-authoritative diagnostics.
4. Cost-adjusted and risk-adjusted performance gates are enforced.
5. Every decision is reproducible from raw snapshot to final intent.

## 13) Practical Performance Statement

No system can guarantee constant profitability. This architecture is designed to maximize expected utility under strict risk controls, reduce overfitting risk, and improve robustness across regime shifts with deterministic reproducibility.
