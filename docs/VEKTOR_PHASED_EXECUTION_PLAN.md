# Vektor Phased Execution Plan

As of: 2026-04-21 (America/Phoenix)

This document is the operating contract for how Vektor gets built from here.

The rule is simple:
- finish a phase robustly before starting the next phase
- no speculative breadth inside a phase
- no UI-first work when backend logic is incomplete
- every phase must leave behind a stable expansion seam for the next one

## 1) Core Build Principle

Vektor is backend-first.

If orchestration, risk, execution, provenance, and data integrity are weak, the rest of the product is cosmetic. The admin console, blog, research page, and public surfaces are downstream of the backend and must reflect backend truth rather than compensate for backend gaps.

## 2) Current Strategic Constraint

Local LLM quality is not good enough for Vektor's specialist-agent quality bar.

Therefore the near-term architecture is:
- OpenClaw on the laptop as the CEO command/orchestration interface
- Vektor backend on a persistent free cloud VM
- specialist agents using hosted multi-vendor APIs
- local models optional only for experimentation, never the primary production rail

## 3) Hosted LLM Decision

### 3.1 Primary Recommendation
- Default worker rail: `Gemini 2.5 Flash-Lite`
- Planner / synthesis / judge rail: `Gemini 2.5 Flash`
- Low-latency fallback rail: `Groq`
- GitHub-native experimentation rail: `GitHub Models`
- Interactive human orchestration rail: `OpenClaw` with GitHub Copilot where useful
- Routing / logging / failover control plane: `Cloudflare AI Gateway`

### 3.2 Why
- `Gemini Flash-Lite` gives the best official free or near-free worker economics.
- `Gemini Flash` is the better planner and synthesis tier.
- `Groq` is valuable for fast specialist loops and fallback routing.
- `GitHub Models` is useful, but its free/public-preview limits are too small to be the main inference budget for a continuously running fund backend.
- `Copilot` is better treated as the developer/operator interaction layer than as the fund's high-volume backend inference substrate.

### 3.3 Architectural Rule
- Do not hard-bind any agent to one vendor.
- Every agent role must resolve through one provider-routing layer.
- Vendor choice must be config-driven per role.
- Provider outages, quota exhaustion, and model downgrades must degrade gracefully and visibly.

## 4) Phase Alpha: Backend Core

Phase Alpha is the whole backend becoming real, stable, and operational.

### 4.1 Scope
- OpenClaw orchestration working end-to-end from CEO command to backend action
- hierarchical and parallel swarm execution
- role-specialized agents with hosted LLM routing
- paper-trading execution with strict risk and policy gates
- real-data-only operation
- sleeve budget enforcement and capital allocation controls
- ability to sit in cash when no valid trade exists
- scheduled and event-driven agent activity
- ML pipeline for regression, classification, and time-series forecasting
- ticker and opportunity discovery agents
- world-news / event-impact scanner agents
- multi-asset intent model and broker abstraction seams
- human-readable deliverables for every specialist and every synthesis step
- blog and research generation pipelines driven by real backend artifacts, not generic copy
- deployment of the backend on a persistent free cloud VM

### 4.2 Alpha Deliverables
- Fund manager orchestration service
- task bus and queueing semantics
- specialist role adapter layer
- provider-router with vendor failover
- strict real-data integrity guard
- risk engine with halt behavior and recovery runbook
- execution policy and sleeve allocator
- deliverable contracts:
  - analyst report
  - composite investment memo
  - execution recommendation
  - audit artifact
  - ML artifact
  - research paper draft
  - blog draft

### 4.3 Alpha Exit Criteria
Alpha is only complete when all of the following are true:
- backend runs continuously on a cloud VM
- OpenClaw can issue control and work commands reliably
- every agent task has lineage, status, symbol, failure reason, and deliverable IDs
- hosted LLM routing is working across at least two vendors
- data-integrity halt stops all downstream work on fallback or invalid provider state
- capital sleeve rules are enforced before execution
- the system can decide not to trade and remain idle without error
- deliverables are readable and decision-usable
- paper broker state, PnL, and admin data are consistent
- daily operation can continue without manual babysitting

### 4.4 Alpha Non-Goals
- no obsession with polished UI
- no premature graph-kb complexity
- no broad investor-facing polish
- no live capital

## 5) Phase Beta: Data, Memory, and Reference Infrastructure

Phase Beta is about turning Vektor into a system that remembers, references, and reuses.

### 5.1 Scope
- ingestion pipeline normalization
- ETL contracts for market, fundamentals, news, social, research, and execution artifacts
- canonical SQL persistence for all generated artifacts
- durable document store semantics for all agent outputs
- referenceable IDs and retrieval APIs
- rebuildable graph projection layer for exploration and lineage
- knowledge namespaces and retention policies

### 5.2 Beta Architectural Rule
- SQL is the source of truth
- graph is a projection, not the canonical store

### 5.3 Beta Deliverables
- unified artifact table strategy
- document and metadata indexing
- retrieval endpoints by:
  - run
  - agent
  - symbol
  - asset class
  - report type
  - decision lineage
- memory policies for:
  - research
  - trades
  - audit
  - development
  - operator commands

### 5.4 Beta Exit Criteria
- every meaningful agent output is persisted as a document artifact
- all artifacts are queryable by lineage and business context
- knowledge rebuild does not lose canonical state
- no backend workflow depends on ad hoc filesystem-only memory
- retrieval is fast enough to support low-token context assembly

## 6) Phase Gamma: Operator OS

Phase Gamma is where the CEO/admin operating system becomes first-class.

### 6.1 Scope
- command-center admin console
- live swarm visibility
- fund-manager controls
- allocation controls by sleeve and asset class
- halt / recover / drain / retry operator controls
- audit drill-downs
- performance and attribution surfaces
- observability and incident reporting

### 6.2 Gamma Exit Criteria
- CEO can see what is running, why it is running, and what it produced
- CEO can pause, resume, halt, drain, and redirect the system
- admin reflects backend truth, not derived guesses
- PnL, research, deliverables, and lineage stay consistent across surfaces

## 7) Phase Delta: Research and Publication Engine

Phase Delta makes Vektor publish-worthy.

### 7.1 Scope
- research-paper workflow
- editorial review and publication workflow
- blog automation from genuine internal findings
- title images and inline figures
- research and blog quality gates
- publication scheduling

### 7.2 Delta Rule
- never publish generic filler
- only publish:
  - original findings
  - strong synthesis
  - high-signal case studies
  - investment-relevant industry analysis

### 7.3 Delta Exit Criteria
- research page reads like a research desk, not a content feed
- blog posts are sourced from real internal work
- two blogs/day is only allowed if quality gates pass
- no random topic generation detached from Vektor's actual research pipeline

## 8) Phase Epsilon: Market Expansion and Institutional Data Adapters

Phase Epsilon adds breadth without destabilizing Alpha/Beta.

### 8.1 Scope
- paid data provider adapters
- institutional-grade market data plug-ins
- more venues and asset classes
- better derivatives and cross-asset abstractions
- better screening and opportunity discovery

### 8.2 Rule
- expansion must plug into stable interfaces already created in Alpha and Beta
- no rewriting core orchestration to add a new provider

### 8.3 Exit Criteria
- new providers can be attached with adapter work, not architectural surgery
- cross-asset routing remains coherent under one risk and capital framework

## 9) Phase Zeta: Compliance and Externalization

Phase Zeta is for legal, investor, and controlled production preparation.

### 9.1 Scope
- compliance posture
- policy evidence
- reporting packages
- investor-ready performance exports
- deployment hardening and security review

### 9.2 Exit Criteria
- operational and reporting artifacts are credible to outside reviewers
- security and secret management are no longer ad hoc
- the system is ready for real compliance work rather than just engineering demos

## 10) What We Work On Now

Current active phase:
- `Phase Alpha`

Current development priority order inside Alpha:
1. provider routing away from local Ollama and into hosted multi-vendor APIs
2. backend orchestration correctness
3. risk / allocation / execution correctness
4. deliverable quality contracts
5. autonomous scheduling and swarm reliability
6. cloud deployment for persistent backend runtime
7. only then, further operator UI refinement

## 11) Hard Rules for All Future Work

- If a task does not materially advance the active phase, it is deferred.
- If a feature cannot be operated or audited, it is incomplete.
- If a deliverable is not readable by the CEO, it is incomplete.
- If a provider or data source cannot degrade safely, it is incomplete.
- If a new capability requires rewriting core layers, the seam was designed incorrectly.

## 12) Official Provider References

- GitHub Copilot requests: [GitHub Docs](https://docs.github.com/en/copilot/concepts/billing/copilot-requests)
- GitHub Models prototyping and API rate limits: [GitHub Docs](https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models)
- Groq billing FAQs: [Groq Docs](https://console.groq.com/docs/billing-faqs)
- Groq rate limits: [Groq Docs](https://console.groq.com/docs/rate-limits)
- Gemini API rate limits: [Google AI for Developers](https://ai.google.dev/gemini-api/docs/rate-limits)
- OpenRouter limits: [OpenRouter Docs](https://openrouter.ai/docs/api/reference/limits)

