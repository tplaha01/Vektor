# Viktor: Canonical Startup Goal Specification

## 1) Mission
Viktor is an AI-native hedge fund startup operating initially in paper-trading mode, built to become a scalable, institutional-grade investment firm with full traceability, persistent memory, and autonomous multi-agent operations across multi-asset markets.

This repository is not a toy bot project. It is the operating system of the firm.

## 2) End-State Vision
- Multi-asset coverage: equities, ETFs, crypto, commodities, futures/indices proxies, derivaties and macro signals.
- Multi-hierarchy org design: CEO/fund-manager orchestrator over specialized departments.
- Multi-agent workforce: role-based agents with explicit scopes, KPIs, and auditable responsibilities.
- Orchestrated decision pipeline: data -> research -> thesis -> risk -> execution -> audit -> learning.
- Persistent memory graph: all decisions, conversations, artifacts, and outcomes indexed for fast recall.
- Assistant-orchestrated development and operations: humans + agents co-running a single operating protocol.
- Startup-grade execution: designed for team growth, investor reporting, compliance posture, and client onboarding.

## 3) Business Requirements (Non-Negotiable)
- Paper-first safety: no live trading activation in this phase.
- Immutable traceability: every material event must carry IDs linking lineage end-to-end.
- Institutional auditability: each decision must explain why it happened, who/what approved it, and what occurred.
- Capital discipline: sleeve-level allocation and budget enforcement before execution.
- Operator control: CEO/admin can inspect, intervene, pause, and override with full logs.
- Continuous research loop: market knowledge updates 24/7 and feeds decision quality.
- Memory persistence: the fund must not "forget" prior work, outcomes, or policy decisions.
- Migration-safe architecture: old behavior remains stable while new capabilities are added incrementally.

## 4) Target Operating Model

### 4.1 Role Hierarchy
- CEO / Founder (human): strategic directives, constraints, approvals, and product direction.
- Fund Manager Agent (orchestrator): converts directives into plans and allocates work/capital.
- Research Department Agents: macro, fundamental, technical, sector, and event-driven research.
- Sentiment Intelligence Agents: social/news sentiment with provenance scoring.
- Trading Agents: convert thesis into execution intent with entry/exit logic.
- Risk + Audit Agents: policy enforcement, deviations detection, and governance monitoring.
- Ops/Infra Agents: uptime, ingest health, data quality, model routing, and incident response.

### 4.2 Canonical Decision Flow
1. Ingest market + external intelligence.
2. Build research reports with provenance.
3. Build thesis mapped to sleeve and conviction.
4. Run policy + budget gate checks.
5. Emit execution intent to paper broker.
6. Capture post-trade telemetry and audit timeline.
7. Index everything to graph memory and update learning context.

## 5) Product Surfaces (Required Pages)

### 5.1 Public Experience
- Landing / marketing page (SSR): narrative, mission, product differentiators, SEO-first.
- Public PnL page: delayed/public-safe performance snapshot and methodology disclosure.
- Public docs page: architecture, risk disclosures, paper-first status, and API references.
- Blog / research publication page: auto-assisted content generated from internal research artifacts.

### 5.2 Internal / Operator Experience
- Admin console: orchestration controls, runtime config, model routing, and incident controls.
- Operations panel: active tasks, queues, blocked decisions, channel health, and ingest health.
- PnL and attribution page: sleeve-level and strategy-level contribution analysis.
- Audit timeline page: full lineage by order/decision/run with immutable IDs.
- Knowledge graph explorer page: what Viktor knows, when it learned it, and source provenance.
- Agent management page: role roster, workload, quality metrics, and handoff visibility.
- Investor portal (future): authenticated LP-facing reports, tear sheets, and communications.

## 6) Canonical Knowledge and Memory Rules
- Every output from every agent is an artifact and must be indexed.
- Every chat/control command is an artifact and must be indexed.
- Every ingest acceptance/rejection is an artifact and must be indexed.
- Every decision/risk/execution event is an artifact and must be indexed.
- Artifacts must include immutable IDs and entity links (run_id, decision_id, order_id, report_id, agent_id).
- Memory is graph-first, persistent, queryable, and suitable for low-token retrieval workflows.

## 7) Multi-Environment Agent Coordination Protocol
All models/agents working on Viktor must follow one shared protocol:

1. Read this `Viktor.md` before planning or coding.
2. Attach all output to an explicit run ID and role.
3. Log intent, changes, and outcomes into the knowledge graph layer.
4. Never bypass policy/risk gates for execution paths.
5. Preserve backward compatibility unless explicitly migrating with tests.
6. Publish concise "what changed and why" summaries as memory artifacts.
7. Resolve conflicts by deferring to this document as source of truth.

## 8) Execution Phases
- Phase A: paper-mode autonomous orchestration and traceability baseline.
- Phase B: quality and scale improvements (richer ingestion, stronger risk, better attribution).
- Phase C: operator/investor surfaces and startup operating cadence.
- Phase D: controlled production hardening and compliance preparation.

## 9) Success Criteria
- The system runs continuously with role-based autonomous workflows.
- Capital is allocated and enforced by sleeve with audit evidence.
- Research-to-execution lineage is queryable in seconds.
- Operator can inspect any decision path from source to order.
- Product has clear public and private surfaces appropriate for startup growth.

## 10) Current Constraint
Until explicitly changed by policy and legal/compliance readiness, Viktor remains paper-trading only.

## 11) Specialist Signal Mandate
Viktor decision quality depends on six dedicated specialist analyst agents whose outputs are all mandatory inputs to the trading thesis:
- `technical_analyst`
- `fundamental_analyst`
- `sentiment_analyst`
- `ml_timeseries_analyst`
- `insight_researcher`
- `hedge_fund_researcher`

The fund manager should receive a synthesized high-grade report that combines these signals before trader execution.

Quality bar:
- Each specialist agent is treated as a domain expert role, not a generic assistant.
- Outputs must be concise, source-backed, and decision-usable (no vague commentary).
- Every report must include actionable findings, confidence, and provenance artifacts.

## 12) OpenClaw Orchestration Mandate
- OpenClaw is a command and research-ingestion orchestration layer.
- OpenClaw may trigger analyst swarms and route structured commands.
- OpenClaw must not have direct trade execution authority.
- Every OpenClaw command/ingest event must be traceable and indexed.

### 12.1 OpenClaw Specialist Routing Policy
- Allowed command targets:
  - `technical_analyst`
  - `fundamental_analyst`
  - `sentiment_analyst`
  - `ml_timeseries_analyst`
  - `insight_researcher`
  - `hedge_fund_researcher`
  - `fund_manager`
  - `trader`
  - `risk_auditor`
  - `signal_swarm`
- `signal_swarm` is the canonical OpenClaw command mode for full multi-signal orchestration.
- OpenClaw ingress can initiate analysis and orchestration only; risk/policy gates remain mandatory for execution.

### 12.2 OpenClaw Traceability Rules
- Every accepted command must record:
  - channel sender context
  - inferred/explicit target role
  - run ID
  - task IDs or signal pack ID
- Every rejected command must record:
  - rejection reason
  - source context
- All of the above must be indexed into the knowledge graph with OpenClaw namespace events.

## 13) Development Governance Files
- `DevViktor.md`: operating contract for development models/agents.
- `Dev_Logs.md`: append-only session log for who changed what and validation status.

These files are mandatory for multi-model/multi-environment development alignment.

## 14) Knowledge Graph Namespace Policy
All knowledge graph events must be namespace-qualified and queryable.  
Examples:
- `development.*`
- `task_bus.*`
- `orchestrator.*`
- `decision_ledger.*`
- `audit_log.*`
- `openclaw.*`

This policy exists to keep retrieval precise, reduce noise, and preserve long-term memory quality.
