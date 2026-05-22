export const blogPostsData = {
  "intro-to-vektor": {
    slug: "intro-to-vektor",
    title: "Vektor Operating Thesis",
    description:
      "Why Vektor starts as a deterministic, paper-first operating platform before AI-assisted allocation is introduced.",
    date: "2026-04-15",
    tags: ["Operating Model", "Paper Trading", "Controls"],
    featured: true,
    readTime: 7,
    author: "Vektor Team",
    content: `# Vektor Operating Thesis

Vektor is being built as a trading operations platform before it is built as an AI allocation engine. That sequence matters.

The first job is to prove that the system can ingest market evidence, construct repeatable features, enforce risk policy, route paper orders, and preserve a decision record that an operator can inspect.

## Why deterministic first

Model work is only useful when the surrounding operating system is reliable. A trading system needs:

- Reconstructable input data
- Explicit feature generation
- Risk checks before execution
- Paper-broker state reconciliation
- Operator recovery controls
- A decision ledger that survives redeploys

The current platform posture is paper-first. Live trading is disabled by default, and performance views are presented as paper operating records rather than audited returns.

## What Vektor should prove

Vektor should prove that market data, features, decisions, orders, fills, and portfolio state can be connected into a traceable workflow. Once that foundation is stable, AI-assisted research and allocation can be layered in without turning the system into a black box.

## The practical standard

The platform is not trying to look futuristic. It is trying to make each trading workflow observable, governable, and recoverable.`,
  },
  "multi-agent-trading": {
    slug: "multi-agent-trading",
    title: "From Signals to Governed Decisions",
    description:
      "How deterministic signal construction, pre-trade checks, and operator review form a controlled paper-trading workflow.",
    date: "2026-04-12",
    tags: ["Signals", "Risk", "Audit"],
    featured: true,
    readTime: 6,
    author: "Vektor Team",
    content: `# From Signals to Governed Decisions

The Vektor workflow is intentionally sequential. A signal should not become an order until the system can show which evidence existed and which checks ran.

## The decision path

1. Market data and portfolio state are normalized.
2. Technical, fundamental, sentiment, and model-ready features are generated.
3. A deterministic policy turns features into a proposal.
4. Risk controls approve, resize, or block the proposal.
5. Approved orders route to the paper broker.
6. The decision and broker response are written back to the ledger.

## Why this structure matters

This structure makes the workflow inspectable. If a paper trade performs poorly, the operator should be able to see whether the input data was stale, whether the feature frame was incomplete, whether risk controls were too loose, or whether execution state failed to reconcile.

## AI later

Future AI work should add research depth and model selection discipline. It should not bypass the deterministic controls that make the platform governable.`,
  },
  "paper-trading-explained": {
    slug: "paper-trading-explained",
    title: "Paper Trading as System Validation",
    description:
      "Paper trading is the default validation posture for Vektor's data, risk, order, and portfolio workflows.",
    date: "2026-04-08",
    tags: ["Paper Trading", "Validation", "Execution"],
    featured: false,
    readTime: 5,
    author: "Vektor Team",
    content: `# Paper Trading as System Validation

Paper trading is not a cosmetic demo mode. In Vektor, it is the production validation posture.

## What paper mode validates

- Provider data freshness
- Feature construction
- Risk-gate behavior
- Order lifecycle handling
- Broker state reconciliation
- Portfolio and PnL views
- Recovery behavior after redeploys or halted runtime states

## What it does not prove

Paper mode does not prove live-market execution quality, audited performance, or investment suitability. It proves that the operating workflow behaves consistently enough to evaluate before capital is placed at risk.

## The correct interpretation

Paper results should be read as engineering evidence. They help answer whether the platform can run, explain itself, recover, and preserve state.`,
  },
  "risk-management-deep-dive": {
    slug: "risk-management-deep-dive",
    title: "Risk Controls Before Execution",
    description:
      "The Vektor risk model puts runtime posture, data integrity, exposure limits, and operator override ahead of paper order routing.",
    date: "2026-04-01",
    tags: ["Risk", "Controls", "Operations"],
    featured: false,
    readTime: 6,
    author: "Vektor Team",
    content: `# Risk Controls Before Execution

Vektor treats risk as a control layer, not as a performance report after the fact.

## Core controls

- Paper-only execution as the default posture
- Live trading disabled unless explicitly configured
- Data-integrity guard before signal use
- Pre-trade risk check before paper order placement
- Allocation policy with reserve cash and budget limits
- Decision ledger for approvals and blocks

## Runtime states

A halted system should be visible and recoverable. The admin console exists to show whether the platform is halted, running in paper mode, enforcing strict controls, or configured for a different operating state.

## Why this is conservative

Conservative defaults make the platform easier to inspect. The goal is to build trust through evidence, not through aggressive claims.`,
  },
};
