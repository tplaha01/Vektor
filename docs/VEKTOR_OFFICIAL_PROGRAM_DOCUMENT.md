# Vektor Official Program Document

As of: 2026-04-23 (America/Phoenix)
Repository: `TradingBot`
Status: authoritative internal build and operations document

## 1. Executive Summary

Vektor is being built as a local-first, AI-native hedge fund operating system.

The final target state is:
- `CEO -> Vektor/OpenClaw -> backend workers`
- OpenClaw remains the CEO interaction layer on the laptop
- the backend runs continuously on a persistent free cloud VM
- specialist agents use hosted vendor APIs rather than weak local models
- the public landing, blog, and research distribution surfaces run on Vercel
- every report, trade, approval, model score, and publication has persistent lineage

This document defines the current state, the remaining work in Phase Alpha, the full phase sequence after Alpha, the target architecture, and the criteria for a final, production-worthy local + vendor + free-VM + Vercel Vektor system.

## 2. Current State Snapshot

### 2.1 Current overall progress
- Phase Alpha progress: `79 / 100`

### 2.2 What is already real
- Backend orchestration exists and is live
- Specialist agent roles exist and run through a hosted multi-vendor LLM router
- Provider cooldowns, failover, concurrency caps, and deferred retries exist
- Strict real-data mode exists
- Paper-only execution exists
- Multi-asset paper execution routes exist for equities, options, forex, and crypto intents
- CEO approval workflow exists for trades, allocation changes, public publication, and major reroutes
- CEO digests and richer CEO queries exist
- Admin war room exists and is wired to runtime state
- Discovery scoring exists and is persisted
- ML scoring exists and now affects actual trade gating logic
- ML thresholds are adaptive by asset class, strategy family, and portfolio state
- Risk gate exists and blocks trades on policy violations
- Performance tracking, audit trail, task history, and knowledge lineage exist
- Blog and research flows exist with internal/public separation controls
- Local soak harness and health monitoring scripts exist

### 2.3 What is still incomplete
- multi-day local soak has not yet been completed and signed off
- persistent free-VM deployment is not yet hardened and proven
- discovery and world scanning need stronger institutional quality
- ML still needs empirical feedback loops from realized outcomes
- risk framework still needs fuller post-trade and thesis-lifecycle behavior
- public/private content promotion is improved, but publication governance can still be tightened

## 3. Phase Alpha: Backend Core and Fund OS

Phase Alpha is about making Vektor real as a backend-native fund operating system before shifting attention to broader platformization or public polish.

### 3.1 Alpha objective
Build a backend that can orchestrate specialists, discover opportunities, enforce policy and risk, request approval where needed, execute safely in paper mode, and persist every important artifact.

### 3.2 Alpha scope
- canonical CEO/Vektor/OpenClaw command layer
- backend-native worker orchestration and swarm execution
- hosted LLM routing with vendor redundancy
- strict real-data-only operation
- paper broker execution under policy and risk gates
- sleeve and asset-class capital allocation controls
- market scanner and world-event discovery
- ML scoring and confidence estimation
- approval workflows and digests
- admin war room and operator control surfaces
- local-first runtime reliability and soak readiness
- cloud-VM deployment preparation

### 3.3 What Vektor should be able to do by Alpha completion
- answer CEO questions about positions, exposure, risk, winners/losers, and pending approvals
- scan what to trade across supported asset classes
- decide not to trade when conditions are weak
- run analyst swarms and produce readable deliverables
- route through risk and approval gates before execution
- execute in paper mode without bypassing policy
- keep a traceable chain from signal to research to decision to trade to attribution
- survive restarts and prolonged uptime without manual babysitting

### 3.4 Alpha remaining checklist
- complete a real `48-72h` local soak with runtime monitoring
- confirm recovery after restart, halt, and deferred queue pressure
- improve discovery ranking and world-scanning quality
- finish ML outcome feedback and threshold tuning loop
- finish deeper risk behavior around thesis degradation and post-trade review
- finalize VM deployment hardening after local soak success

### 3.5 Alpha exit criteria
Alpha is only complete when all of the following are true:
- Vektor survives a local `48-72h` soak cleanly
- no queue corruption, duplicate execution, or runtime drift appears
- all gating and approval flows remain stable under provider throttling
- discovery and no-trade behavior are credible and explainable
- ML scoring is a meaningful part of approval and execution control
- paper broker state, performance tracking, and admin views remain consistent
- backend is ready to move to the free VM without using the cloud as a debugging crutch

## 4. Phase Beta: Data, Memory, and Knowledge Infrastructure

### 4.1 Beta objective
Turn Vektor into a persistent memory system that stores and references every meaningful internal artifact.

### 4.2 Beta scope
- canonical document storage for reports, tasks, decisions, approvals, and model outputs
- durable retrieval by run, symbol, agent, asset class, and lineage
- graph projection layer built from canonical storage rather than replacing it
- knowledge retention policies and namespaces
- reusable research memory for future decisions

### 4.3 What Vektor should be able to do by Beta completion
- answer with direct provenance and document references
- reconstruct why a trade happened and what evidence was used
- show what each agent found, who consumed it, and what output it influenced
- use past findings as real working memory rather than ad hoc context

### 4.4 Beta exit criteria
- every meaningful artifact is persisted as a queryable document
- knowledge rebuild does not lose canonical business state
- operator and agent retrieval flows are fast enough for practical use
- no important workflow depends on volatile, unindexed memory

## 5. Phase Gamma: Operator OS and Internal CRM

### 5.1 Gamma objective
Make admin the real operating system for the fund rather than a monitoring dashboard.

### 5.2 Gamma scope
- fully structured admin command center
- live per-agent process visibility
- staged wave inspection, pack inspection, and approval operations
- allocation control and intervention controls
- market watch, research oversight, and decision review surfaces
- audit and performance drill-downs
- dense, non-duplicative CRM-like information architecture

### 5.3 What Vektor should be able to do by Gamma completion
- show the CEO exactly what every agent is doing right now
- allow intervention, pause, reroute, retry, cancel, and approve from one surface
- surface operator-grade digests, alerts, and incident context
- keep every admin tab meaningful rather than duplicative

### 5.4 Gamma exit criteria
- admin reflects backend truth directly
- CEO can operate the fund from admin without chasing separate tools
- live processes, decisions, approvals, and outputs are all inspectable and consistent

## 6. Phase Delta: Research and Publication Engine

### 6.1 Delta objective
Create a publication system that turns internal work into high-quality, approval-gated public content.

### 6.2 Delta scope
- internal-only by default for generated content
- explicit promotion workflow to public research and public blog
- editorial review queue and approval loop
- research papers sourced from actual fund discovery and synthesis
- blog-next as the public blog distribution surface
- readable, evidence-based publication style rather than filler content

### 6.3 What Vektor should be able to do by Delta completion
- draft market briefs, case studies, and research papers from internal evidence
- submit content to CEO review before publication
- publish only approved content to public surfaces
- keep public content aligned with the actual internal research pipeline

### 6.4 Delta exit criteria
- no generic or random publication pipeline remains
- every public article has internal provenance
- approval-gated publication is the default operating path

## 7. Phase Epsilon: Persistent Infrastructure and Expansion

### 7.1 Epsilon objective
Move from local-only operation to persistent remote runtime without sacrificing control or reliability.

### 7.2 Epsilon scope
- persistent free cloud VM backend deployment
- static public IP
- supervised startup and restart behavior
- reboot recovery
- health checks, log rotation, backup rotation, and remote observability
- adapter seams for stronger paid data vendors later
- more stable cross-asset support and venue expansion

### 7.3 What Vektor should be able to do by Epsilon completion
- run continuously in paper mode on a free VM
- keep OpenClaw on the laptop as the CEO interface
- maintain stable public web surfaces on Vercel
- operate as a remotely hosted but locally controlled fund OS

### 7.4 Epsilon exit criteria
- backend survives reboot and restart events automatically
- backups and logs are trustworthy
- remote runtime is no less auditable than local runtime
- public surfaces remain separated from internal control surfaces

## 8. Phase Zeta: Final Operating Standard

### 8.1 Zeta objective
Bring Vektor to a hardened, investor-facing, externally defensible operational standard.

### 8.2 Zeta scope
- investor-grade reporting
- compliance preparation and policy evidence
- security hardening and secret management maturity
- performance exports and track-record packaging
- stable vendor abstraction for paid data and stronger model providers
- empirical tuning loops from real paper-trading outcomes

### 8.3 What Vektor should be able to do by Zeta completion
- produce credible reporting for advisors, accelerators, and outside reviewers
- preserve full operational and research lineage
- upgrade vendors without architectural surgery
- operate like a serious fund platform rather than a prototype

### 8.4 Zeta exit criteria
- external artifacts are credible and auditable
- operational security is no longer ad hoc
- the system can support real compliance work rather than only engineering demos

## 9. Final Target Architecture

### 9.1 CEO layer
- CEO interacts with Vektor through OpenClaw/Discord and admin
- natural-language queries and explicit control commands are both supported
- approvals, digests, and interventions flow through Vektor, not directly through backend internals

### 9.2 Runtime layer
- backend workers run continuously on a free VM
- orchestrator, task bus, policy gate, approval center, risk engine, and execution adapters live here
- hosted LLM vendors supply analyst/model synthesis capacity

### 9.3 Memory and data layer
- SQL is canonical
- graph is a projection for exploration and visualization
- every trade, report, and approval has durable IDs and lineage

### 9.4 Public surface layer
- Vercel hosts:
  - landing site
  - public blog
  - public research surfaces
- public output is fed from approved backend content only

### 9.5 Core rule
Do not use cloud deployment or public UI polish to hide unresolved backend problems. The correct order remains:
- local correctness
- local soak
- persistent VM deployment
- public Vercel distribution
- external-grade hardening

## 10. Recommended Immediate Execution Order

### 10.1 Next steps after this document
1. run the real `48-72h` local soak
2. review soak logs for queue, provider, and recovery failures
3. tighten remaining discovery/risk/ML gaps found by soak
4. only after that, complete free-VM deployment hardening
5. then continue Beta and Gamma work without breaking Alpha reliability

### 10.2 What not to prioritize right now
- cosmetic frontend work that does not improve operations
- more public-facing branding work
- publication quality work detached from internal research quality
- cloud deployment before local soak signoff

## 11. Final Standard for Vektor

When the full program is complete, Vektor should be able to:
- act as the canonical fund control authority for the CEO
- discover opportunities, reject weak ones, and request approvals on strong ones
- coordinate specialist swarms under hosted vendor routing
- enforce capital, risk, and thesis discipline before execution
- persist and explain every decision in human-readable form
- run continuously on a free VM while public surfaces are served through Vercel
- separate internal knowledge, public publication, and operator control cleanly
- generate a defensible track record and supporting documentation for real external review

## 12. Official Status of This Document

This document is intended to be the authoritative internal roadmap and operating specification for the remaining buildout of Vektor from the current Phase Alpha state to the final local + vendor + free-VM + Vercel architecture.
