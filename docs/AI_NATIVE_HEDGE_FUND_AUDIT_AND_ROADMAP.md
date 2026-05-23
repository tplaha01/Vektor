# AI-Native Hedge Fund Conversion Audit and Roadmap

As of: 2026-04-16 (America/Phoenix)
Repository: `TradingBot`

## 1) Current-State Audit (What You Actually Have)

Your current codebase is a strong single-bot paper-trading system, not yet a multi-agent hedge fund platform.

Observed architecture:
- FastAPI backend with one autonomous loop (`backend/app/strategies/auto_trader.py`) scanning a fixed watchlist.
- Hybrid signal model (`backend/app/strategies/hybrid.py`) combines:
  - Technical score
  - Fundamental score
  - Headline sentiment (Finnhub + FinBERT/VADER)
  - Optional LightGBM alpha model
- Paper broker only (`backend/app/broker/paper.py`) with local SQLite persistence.
- Risk layer exists (`backend/app/risk/engine.py`) with sizing, drawdown breaker, and ATR stop/TP.
- Backtesting engine exists (`backend/app/backtest/engine.py`) but is still single-strategy and single-orchestrator.
- Frontend dashboard is trader-oriented monitoring UI, not an organizational operating system.

What this means:
- You have a useful execution and analytics kernel.
- You do not yet have firm-level orchestration, role isolation, cross-asset mandate logic, or institutional controls.

## 2) Gap Analysis vs "AI-Native Hedge Fund Startup"

Critical gaps to close:
- No fund-level capital allocator across strategy sleeves (long-term, recurring DCA, intraday, event-driven).
- No role-separated research departments (macro, news, social sentiment, alternatives, regime).
- No continuous multi-agent memory and handoff protocol.
- No formal investment committee workflow (thesis -> challenge -> approve -> execute -> post-mortem).
- No compliance/mandate engine (client policy checks, mandate constraints, concentration rules by sleeve).
- No cross-asset venue abstraction (equities/crypto/futures/options/FX with unified intent model).
- No robust observability and SRE layer for 24/7 operations.
- No reward/penalty loop for agent quality and drift.
- No incident management or kill-switch governance beyond drawdown breaker.
- No data lineage and research provenance guarantees for every decision.

## 3) External Benchmark Notes (and Product Gaps to Exploit)

### Event Horizon Labs (`ehl.markets`)
Public positioning emphasizes:
- AI-native investing firm
- Parallel agents
- Continuous research loop and learning memory

Gap you can exploit:
- Build transparent governance and auditable decision lineage from day 1 (their public materials are vision-heavy, low implementation detail).

### virattt/ai-hedge-fund
Strong educational multi-agent concept, but explicitly states:
- Proof of concept
- Educational use only
- No real trading execution

Gap you can exploit:
- Production-grade reliability, controls, and operational governance (not just agent personas).

### AutoHedge
Strong execution-centric framing with risk-first language.

Gap you can exploit:
- Institutional research organization model + committee workflow + deep post-trade audit and learning loop.

### Street Of Walls hedge fund structure reference
Useful canonical fund roles:
- Research analyst, trader, PM, risk manager, IR/CFO/CAO functions.

Gap you can exploit:
- Encode the full structure directly into agent roles, data contracts, and enforcement policies.

## 4) Directly Applied from `everything-codex` Pattern

You asked to use `/agents` and `/subagents` patterns. This repo now includes:
- `agents/` markdown role files (agent interface style).
- `subagents/` role docs.
- `.codex/config.toml` and `.codex/agents/*.toml` for Codex multi-agent orchestration.

These are adapted to hedge-fund operations instead of generic software coding roles.

## 5) Target Operating Model (Your AI-Native Firm)

You (CEO/Fund Manager) set mandate and high-level risk budget.

Orchestrator layer:
- Fund Manager Orchestrator: sleeve budget, mandate routing, final approvals.
- Ops Orchestrator: scheduling, retries, incidents, health checks.

Research layer:
- Macro Research Agent
- Fundamentals Research Agent
- Technical/Market Microstructure Agent
- News and Event Agent
- X/Social Sentiment Agent
- Alt-Data Agent

Decision layer:
- Thesis Synthesizer
- Debate/Counterparty Agent (bear case)
- Portfolio Allocator
- Risk Committee Agent

Execution layer:
- Trader Agent(s) per venue/asset class
- Order Quality Agent (slippage/fill analysis)

Control layer:
- Audit Agent
- Compliance/Mandate Agent
- Performance Attribution Agent
- Drift/Model Risk Agent

## 6) Build Roadmap (Paper-First, Startup-Ready)

### Phase 1: Platformization (now)
- Introduce explicit agent contracts and role ownership.
- Separate research outputs from execution intents.
- Add immutable decision ledger and provenance IDs.

### Phase 2: Multi-Sleeve Capital Allocation
- Implement fund-level allocator:
  - Long-term sleeve
  - Recurring investment sleeve
  - Tactical/day-trading sleeve
- Add hard and soft constraints per sleeve.

### Phase 3: Cross-Asset Expansion
- Add asset adapters for equities + crypto first, then futures/options.
- Unified signal schema and risk-normalized position sizing.

### Phase 4: Institutional Controls
- Add policy engine (mandate checks, blocked assets, exposure limits).
- Add incident and kill-switch workflow with escalation.
- Add audit trail and post-trade attribution by agent/sleeve.

### Phase 5: Client-Readiness Layer
- Investor reporting pack generation.
- Fee/watermark/accounting simulation.
- Multi-client sub-account and mandate isolation.

## 7) Definition of Done for "AI-Native Hedge Fund Core"

You are not done until all of these are true:
- Every trade has a signed chain: data -> research -> thesis -> risk approval -> execution -> attribution.
- Capital allocation is dynamic and sleeve-based, not hard-coded per ticker.
- Agents can run continuously with health checks, retries, and safe degradation.
- Control agents can stop harmful behavior automatically.
- Performance reporting is per agent, per strategy, per sleeve, and portfolio aggregate.
- Full paper-trading operation can run 24/7 for at least 30 days without manual babysitting.

## 8) Constraints Acknowledged (Your Context)

Because you are running paper-first as an international student:
- Keep live execution disabled by default.
- Focus on validated process quality, not PnL vanity metrics.
- Treat this as a startup operating system that can later support regulated client onboarding.

## 9) OpenClaw Fit (Recommended)

OpenClaw is useful here if positioned as an automation/control-plane extension:
- Use for continuous research intake, scheduling, and multi-channel operations.
- Do not use as direct order authority.
- Keep all trade approvals inside backend risk/compliance gates.

Reference implementation notes are in:
- `docs/OPENCLAW_INTEGRATION_PLAN.md`

## 10) Sources

- https://github.com/affaan-m/everything-codex
- https://raw.githubusercontent.com/affaan-m/everything-codex/main/.codex/config.toml
- https://raw.githubusercontent.com/affaan-m/everything-codex/main/.codex/agents/explorer.toml
- https://developers.openai.com/codex/
- https://github.com/openclaw/openclaw
- https://raw.githubusercontent.com/openclaw/openclaw/main/README.md
- https://docs.openclaw.ai/
- https://www.ehl.markets/
- https://ehl.markets/about
- https://github.com/virattt/ai-hedge-fund
- https://raw.githubusercontent.com/virattt/ai-hedge-fund/main/README.md
- https://github.com/The-Swarm-Corporation/AutoHedge
- https://raw.githubusercontent.com/The-Swarm-Corporation/AutoHedge/main/README.md
- https://streetofwalls.com/finance-training-courses/hedge-fund-training/hedge-fund-overview/
