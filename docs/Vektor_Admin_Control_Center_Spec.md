# Vektor Admin Control Center
## Product Specification & UI Architecture

**Version**: 2.0 (Post-Phase-Alpha)  
**Date**: 2026-05-23  
**Audience**: Vektor engineering team + CEO/Fund Manager  
**Status**: Complete specification for production implementation  

---

## Executive Summary

The **Vektor Admin Control Center** is the **mission-critical nerve center** for the fund manager (CEO) to orchestrate, monitor, and govern all aspects of the Vektor operating system.

**Not a dashboard.** Not analytics visualizations. A **control center**:
- Real-time operational health + active intervention points
- Capital discipline + approval workflows
- Risk oversight + policy enforcement
- Research discovery + thesis tracking
- Agent workforce management + runtime control
- Decision lineage + outcome audit trails
- Multi-vendor LLM orchestration + failover management

This spec defines:
1. **Overall app architecture** (web-based control center)
2. **11 major control panels** with subsections
3. **Information hierarchy** (what operators see, in what order, at what detail level)
4. **Intervention patterns** (how to pause, override, approve, reset)
5. **Data flows** (what syncs, how often, what triggers alerts)
6. **Design principles** (institutional, not flashy)

---

## Part 1: Architecture Decision & Deployment Model

### 1.1 Recommended Topology

**Answer: Keep it simple. Don't build a desktop app.**

```
Recommended Architecture:
├── Landing Site (Static + Content CMS)
│   ├── Homepage + pitch
│   ├── How it works (explainer)
│   ├── Blog + research (auto-fed from backend)
│   └── Public PnL board (read-only, delayed data)
│
├── Admin Control Center (React SPA)
│   ├── Full operator console
│   ├── Real-time control + decision-making
│   ├── Approval workflows + CEO digests
│   ├── Runtime orchestration + agent management
│   └── Risk + capital discipline
│
└── Backend VM (FastAPI)
    ├── Fund orchestrator
    ├── Decision ledger + knowledge graph
    ├── Agent runtime + OpenClaw command router
    ├── Risk gates + policy enforcement
    ├── Execution adapter (paper/live bridge)
    └── Admin API endpoints
```

**Why NOT a desktop app?**
- Complexity + maintenance burden (Electron/PyQt vs web)
- Harder to deploy updates (web = instant, no reinstall)
- Harder to scale (desktop = single machine, web = CDN + cloud)
- Remote access requires VPN anyway (web already solves this)
- Team collaboration easier on web (shared workspace)
- Mobile access for off-hours monitoring (web responsive)

**Why this topology is right for a startup:**
- Landing site educates investors + users (separate concern)
- Admin app is **the real product** (sophisticated operator console)
- Backend is stateless + horizontally scalable
- Single deployment pipeline (no sync between desktop + cloud)
- Clear separation of concerns (public vs private, static vs dynamic)

---

## Part 2: Control Center Information Architecture

### 2.1 Top-Level Navigation (Sidebar)

The left sidebar is the **control hierarchy**. Each item is a major operational domain.

```
VEKTOR CONTROL CENTER
┌─────────────────────────────────────┐
│ Admin Panel                         │
├─────────────────────────────────────┤
│ ① OVERVIEW                          │  ← Current fund state at a glance
│ ② RESEARCH & DISCOVERY              │  ← Active investment ideas
│ ③ THESES & POSITIONS                │  ← Active bets + tracking
│ ④ RISK & POLICY                     │  ← Capital limits + constraints
│ ⑤ EXECUTION & ORDERS                │  ← Trade management + fills
│ ⑥ AGENTS & RUNTIME                  │  ← Workforce orchestration
│ ⑦ APPROVALS & CEO DIGESTS           │  ← Decisions requiring your input
│ ⑧ AUDIT & LINEAGE                   │  ← Decision history + traceability
│ ⑨ MARKET CONTEXT                    │  ← Macro + regime state
│ ⑩ SETTINGS & CONFIGURATION          │  ← System tuning + policies
│ ⑪ KNOWLEDGE GRAPH & MEMORY          │  ← Fund memory + learning
└─────────────────────────────────────┘
```

**Design principles**:
- Items ordered by **CEO decision flow**: overview → research → decisions → risk → execution
- No item is cosmetic. Every panel enables actual control.
- Deep drill-down available but not required (summaries first)
- Red alerts surface at every level (don't hide problems)

---

## Part 3: Detailed Control Panel Specifications

### ① OVERVIEW (Landing Panel)

**Purpose**: At-a-glance fund health. The first thing you see when you log in.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ FUND STATUS (Real-time)                                     │
├─────────────────────────────────────────────────────────────┤
│
│ KPI Tiles (4 tiles, horizontally arranged):
│ ┌──────────────┬──────────────┬──────────────┬──────────────┐
│ │ NAV          │ Monthly PnL  │ Sharpe Ratio │ Max Drawdown │
│ │ $2,547,320   │ +$43,200 (+2.1%) │ 1.24     │ -3.2%        │
│ │ ↑ from last  │ vs bench: +0.8% │ 30d rolling  │ from HWM   │
│ │ $2,498,120   │                │              │            │
│ └──────────────┴──────────────┴──────────────┴──────────────┘
│
│ Status Summary (3 rows):
│ ┌─────────────────────────────────────────────────────────────┐
│ │ RUNTIME STATUS: ✅ HEALTHY                                  │
│ │   Orchestrator: ACTIVE | Last heartbeat: 2s ago             │
│ │   Data pipeline: 100% | ML models: LOADED | Broker: READY   │
│ │   Agents active: 6/6 | Pending tasks: 2                     │
│ │                                                              │
│ │ PORTFOLIO EXPOSURE: 68% DEPLOYED                             │
│ │   Equities: $1,732K (68%) | Cash: $815K (32%)              │
│ │   Shorts: $127K | Long/Short ratio: 13.6x                  │
│ │   Gross leverage: 1.2x | Max allowed: 1.5x ✅              │
│ │                                                              │
│ │ RISK STATUS: ✅ WITHIN LIMITS                               │
│ │   Portfolio VaR (95%, 1d): $28.4K (-1.1%)                  │
│ │   Expected drawdown (6m): -6.3% | Limit: -15% ✅           │
│ │   Sector concentration: Largest 3 = 31% | Limit: 40% ✅    │
│ └─────────────────────────────────────────────────────────────┘
│
│ Active Alerts (if any):
│ ┌─────────────────────────────────────────────────────────────┐
│ │ ⚠️  2 PENDING APPROVALS (Agent discovery requires sign-off)  │
│ │ 🔵 1 INFO: Risk model retraining scheduled 2026-05-25 03:00 UTC │
│ │ ⏸️  1 PAUSED TASK: "Tech sector scout" waiting manual input  │
│ └─────────────────────────────────────────────────────────────┘
│
│ Quick Action Buttons (bottom):
│ [View Full P&L] [View Holdings] [Approve Pending] [Control Center]
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Real-time (WebSocket for NAV/status, 1s refresh)

**User actions available**:
- Click any KPI tile to drill down (nav history, daily PnL attribution, etc.)
- Click "Approve Pending" to jump to approvals panel
- Click "Control Center" to go to runtime status

---

### ② RESEARCH & DISCOVERY

**Purpose**: Track all active research ideas, hypotheses, and discovery signals. This is where agents surface opportunities.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ RESEARCH & DISCOVERY                                        │
├─────────────────────────────────────────────────────────────┤
│
│ Filter Bar (top):
│ Status: [ALL] [ACTIVE] [ARCHIVED] [REJECTED]
│ Type: [ALL] [MACRO] [SECTOR] [FUNDAMENTAL] [TECHNICAL] [EVENT]
│ Conviction: [ALL] [HIGH] [MEDIUM] [LOW]
│ Source: [ALL] [AGENT_DISCOVERY] [CEO_INPUT] [MARKET_SCAN]
│
│ RESEARCH IDEAS TABLE:
│ ┌──────┬──────────────┬──────────┬────────────┬───────┬───────┐
│ │ ID   │ TITLE        │ TYPE     │ CONVICTION │ DAYS  │ STATUS│
│ │      │              │          │ (SIGNAL%)  │ LIVE  │       │
│ ├──────┼──────────────┼──────────┼────────────┼───────┼───────┤
│ │ R-47 │ Fed pivot    │ MACRO    │ 62% ⬆️     │ 8d    │ 🟢 ACT│
│ │      │ (lower rates)│          │ +8% WoW    │       │ IVE   │
│ ├──────┼──────────────┼──────────┼────────────┼───────┼───────┤
│ │ R-46 │ NVIDIA AI    │ FUND     │ 71% ⬆️     │ 3d    │ 🟢 ACT│
│ │      │ capex surge  │          │ +12% WoW   │       │ IVE   │
│ ├──────┼──────────────┼──────────┼────────────┼───────┼───────┤
│ │ R-45 │ Energy       │ SECTOR   │ 41% ➡️     │ 12d   │ 🟡 WAT│
│ │      │ transition   │          │ -5% WoW    │       │ CH    │
│ └──────┴──────────────┴──────────┴────────────┴───────┴───────┘
│
│ SELECTED IDEA DETAIL (click to expand):
│ ┌─────────────────────────────────────────────────────────┐
│ │ R-47: Fed Policy Pivot (MACRO)                          │
│ │                                                         │
│ │ SOURCE: OpenClaw macro scan (2026-05-20)               │
│ │ AGENTS: macro_analyst (72h), sentiment_analyzer (48h)  │
│ │                                                         │
│ │ THESIS:                                                 │
│ │ Fed pausing rate hikes, market pricing 3 cuts by Q4.  │
│ │ Duration-sensitive assets (bonds, tech) should outper. │
│ │ Conviction rising as inflation data cools.             │
│ │                                                         │
│ │ KEY SIGNALS (conviction flow):                         │
│ │ ✅ CPI surprise: -0.2% vs expected (4d ago) → +15%    │
│ │ ✅ Fed fund futures: 50bps cut by Sep → +8%            │
│ │ ✅ Media tone: 87% bullish (vs 67% baseline) → +12%   │
│ │ ⚠️  Payrolls strong (190k) → -8% (conflicting signal) │
│ │                                                         │
│ │ THESIS ASSIGNMENTS:                                     │
│ │ [T-12] "Long duration" - 68% conviction, $400K sleeve │
│ │ [T-13] "Tech rotation" - 54% conviction, $200K sleeve │
│ │                                                         │
│ │ RECENT UPDATES:                                         │
│ │ 2026-05-23 14:30 | Updated conviction +8% (CPI data)  │
│ │ 2026-05-22 11:15 | Created thesis T-13 (sentiment shift)│
│ │                                                         │
│ │ [Archive] [Link to Thesis] [View in Audit Trail]      │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Batched (new ideas every 1–2 hours when agents discover, signals update hourly)

**User actions available**:
- **Create thesis** from idea (converts research into tracked bet)
- **Archive idea** (mark as solved or irrelevant)
- **Adjust conviction manually** (if you disagree with signal blend)
- **Pause discovery** on specific idea (don't create more theses from it)
- **View lineage** (trace back to agent work, data sources, reasoning)

---

### ③ THESES & POSITIONS

**Purpose**: Active investment bets. Track thesis conviction, allocations, performance, and exit signals.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ THESES & POSITIONS                                          │
├─────────────────────────────────────────────────────────────┤
│
│ Filter/Sort:
│ Status: [ALL] [ACTIVE] [CLOSING] [CLOSED]
│ Sort by: [CONVICTION] [PnL%] [ALLOCATION] [AGE]
│
│ THESIS TRACKER TABLE:
│ ┌─────┬──────────────┬────────┬─────────┬────────┬────────┐
│ │ ID  │ THESIS       │ CONV   │ ALLOC   │ PnL    │ EXIT   │
│ │     │              │ %      │ ($K)    │ ($K)   │ SIGNAL │
│ ├─────┼──────────────┼────────┼─────────┼────────┼────────┤
│ │ T-12│ Long         │ 68%    │ $400K   │ +$18.2K│ ⬆️ 71% │
│ │     │ duration     │ ⬆️ +8% │ 15.7%   │ +4.6%  │ (HOLD) │
│ ├─────┼──────────────┼────────┼─────────┼────────┼────────┤
│ │ T-11│ Tech         │ 54%    │ $200K   │ -$3.1K │ ⬇️ 38% │
│ │     │ rotation     │ ➡️ -2% │ 7.9%    │ -1.5%  │ (WARN) │
│ ├─────┼──────────────┼────────┼─────────┼────────┼────────┤
│ │ T-10│ Energy       │ 41%    │ $180K   │ +$7.4K │ ➡️ 42% │
│ │     │ transition   │ ⬇️ -5% │ 7.1%    │ +4.1%  │ (HOLD) │
│ └─────┴──────────────┴────────┴─────────┴────────┴────────┘
│
│ THESIS DETAIL PANEL (click to expand):
│ ┌─────────────────────────────────────────────────────────┐
│ │ T-12: Long Duration (Fed Pivot Play)                    │
│ │                                                         │
│ │ CONVICTION TRAJECTORY:                                  │
│ │ [████████████████░░] 68% (↑ from 60% 5d ago)           │
│ │ Recent: +8% (CPI data) | 30d trend: +12%               │
│ │ Signal composition: Fed futures 30% | CPI 25% | ...    │
│ │                                                         │
│ │ ALLOCATION:                                             │
│ │ Current: $400K (15.7% of AUM) | Max: $500K (20%)      │
│ │ Available to deploy: $100K | ⏸ Can't deploy yet       │
│ │ Reason: 2 positions at size limits pending review      │
│ │                                                         │
│ │ HOLDINGS (linked positions):                            │
│ │ ├─ BND.US: $280K | PnL: +$15.2K | Entered: 2026-05-10 │
│ │ ├─ TMF.US: $120K | PnL: +$3.0K | Entered: 2026-05-15  │
│ │ └─ GOVT.US: $80K | PnL: +$1.5K | Entered: 2026-05-18  │
│ │                                                         │
│ │ EXIT SIGNAL MONITOR:                                    │
│ │ Conviction floor: 50% | Current: 68% | Margin: +18%    │
│ │ Warning threshold: 55% | Alert threshold: 50%          │
│ │ Max loss allowed: -$20K | Current: +$18.2K ✅          │
│ │                                                         │
│ │ RECENT UPDATES:                                         │
│ │ 2026-05-23 10:15 | Conviction +8% (Fed speakers tone) │
│ │ 2026-05-22 14:30 | Position added: GOVT.US $80K       │
│ │ 2026-05-20 09:00 | Created thesis (from research R-47) │
│ │                                                         │
│ │ [Edit conviction] [Increase allocation] [Review exits] │
│ │ [Close thesis] [View lineage] [View audit trail]       │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Real-time (exit signals calculated every 5min)

**User actions available**:
- **Adjust conviction manually** (override AI signal if you disagree)
- **Increase/decrease allocation** (control capital deployment)
- **Review & approve exits** (when conviction hits threshold)
- **Close thesis early** (manual stop-loss or change of mind)
- **View all holdings** for thesis
- **View AI reasoning** (SHAP values, signal decomposition)

---

### ④ RISK & POLICY

**Purpose**: Real-time risk monitoring + policy enforcement. Guardrails for the entire operation.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ RISK & POLICY                                               │
├─────────────────────────────────────────────────────────────┤
│
│ PORTFOLIO RISK DASHBOARD:
│ ┌─────────────────────────────────────────────────────────┐
│ │ VALUE AT RISK (1d, 95% confidence)                      │
│ │ Current: $28.4K (-1.1%) | Historical avg: $31.2K       │
│ │ Max allowed: $50K | Margin: $21.6K (43%) ✅             │
│ │ [Chart: 30d rolling VaR]                                │
│ │                                                         │
│ │ EXPECTED SHORTFALL (CVaR, tail risk)                    │
│ │ Current: $45.8K (-1.8%) | Max allowed: $80K ✅          │
│ │ Interpretation: worst 5% of days costs $45.8K avg      │
│ │                                                         │
│ │ MAXIMUM DRAWDOWN (from high water mark)                 │
│ │ Current: -3.2% | Max allowed: -15% | Margin: -11.8% ✅ │
│ │ HWM: $2,631.2K (2026-04-15)                            │
│ │ Current NAV: $2,547.3K                                  │
│ │                                                         │
│ │ GROSS LEVERAGE                                          │
│ │ Current: 1.2x | Max allowed: 1.5x | Margin: 0.3x ✅    │
│ │ Long gross: 1.15x | Short gross: 0.05x                 │
│ │                                                         │
│ │ SHARPE RATIO (rolling 30d)                              │
│ │ Current: 1.24 | Target: > 1.0 ✅                        │
│ │ 30d return: +2.1% | 30d vol: 1.7%                      │
│ └─────────────────────────────────────────────────────────┘
│
│ POLICY ENFORCEMENT:
│ ┌─────────────────────────────────────────────────────────┐
│ │ CAPITAL ALLOCATION LIMITS                               │
│ │ Sector concentration (top 3):                           │
│ │   ├─ Tech: 25% | Max: 35% | Margin: 10% ✅             │
│ │   ├─ Finance: 18% | Max: 30% | Margin: 12% ✅          │
│ │   └─ Industrials: 12% | Max: 25% | Margin: 13% ✅      │
│ │                                                         │
│ │ Correlation risk (highest pair):                        │
│ │   AAPL + MSFT: 0.87 (expected: 0.80-0.90) ✅           │
│ │                                                         │
│ │ Position size limits:                                   │
│ │   Max single position: 8% | Current max: 6.2% ✅       │
│ │   Min position to trade: $10K | Current min: $42K ✅   │
│ │                                                         │
│ │ MARKET HOURS & SESSION RULES                            │
│ │ Current time: 2026-05-23 16:45:00 UTC                  │
│ │ US session: 🟢 OPEN (closes 21:00 UTC)                 │
│ │ Crypto: 🟢 24/5                                         │
│ │ FX: 🟢 OPEN (closes 21:00 UTC Friday)                  │
│ │ Options: 🟢 OPEN                                        │
│ │                                                         │
│ │ TRADE APPROVAL THRESHOLDS                               │
│ │ Any trade > $100K notional: requires your approval     │
│ │ Any trade against active thesis: auto-approved         │
│ │ Any trade in illiquid asset: requires your approval    │
│ │                                                         │
│ │ [Adjust thresholds] [View policy log] [Override rule]  │
│ └─────────────────────────────────────────────────────────┘
│
│ RISK ALERTS (if breached):
│ ┌─────────────────────────────────────────────────────────┐
│ │ ⚠️  NONE CURRENTLY                                      │
│ │                                                         │
│ │ Recent violations (last 7d):                            │
│ │ • 2026-05-20: Sector concentration on Tech +1% overage │
│ │   (auto-corrected by policy gate, trade blocked)       │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Real-time (recalculated on every trade, 1min for metrics)

**User actions available**:
- **Adjust risk limits** (change VaR threshold, max drawdown, etc.)
- **Adjust policy thresholds** (change approval size, sector limits)
- **Override rule** (bypass policy gate for specific trade, logs it)
- **View risk ledger** (all policy decisions + overrides + why)
- **Stress test** (what if this trade? what if volatility spikes?)

---

### ⑤ EXECUTION & ORDERS

**Purpose**: Trade lifecycle management. Orders, fills, costs, execution quality.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ EXECUTION & ORDERS                                          │
├─────────────────────────────────────────────────────────────┤
│
│ Filter/View:
│ Status: [ALL] [PENDING] [FILLED] [PARTIAL] [CANCELLED]
│ Time: [TODAY] [THIS WEEK] [THIS MONTH] [ALL]
│ Type: [ALL] [BUY] [SELL] [SHORT]
│ Asset class: [ALL] [EQUITIES] [OPTIONS] [FOREX] [CRYPTO]
│
│ ORDERS TABLE (most recent first):
│ ┌─────┬────────┬──────────┬───────┬─────────┬──────────┬────────┐
│ │ ID  │ STATUS │ SYMBOL   │ SIZE  │ PRICE   │ EXEC TIME│ SLIPPAGE
│ ├─────┼────────┼──────────┼───────┼─────────┼──────────┼────────┤
│ │ O-89│ ✅ FILL│ BND.US   │ 2800u │ $101.23 │ 0.3s     │ -0.6bps
│ │     │        │ Long     │       │ avg     │ 14:32:15 │        
│ ├─────┼────────┼──────────┼───────┼─────────┼──────────┼────────┤
│ │ O-88│ ✅ FILL│ TMF.US   │ 1200u │ $89.47  │ 0.2s     │ -0.2bps
│ │     │        │ Long     │       │ avg     │ 14:28:42 │        
│ ├─────┼────────┼──────────┼───────┼─────────┼──────────┼────────┤
│ │ O-87│ ⏳ PD  │ GOVT.US  │ 800u  │ $104.18 │ pending  │ -      
│ │     │ (await │ Long     │       │ (limit) │ 1.2s ago │        
│ │     │ fill)  │          │       │         │          │        
│ └─────┴────────┴──────────┴───────┴─────────┴──────────┴────────┘
│
│ ORDER DETAIL PANEL (click to expand):
│ ┌─────────────────────────────────────────────────────────┐
│ │ ORDER O-89: BND.US LONG                                 │
│ │                                                         │
│ │ EXECUTION CONTEXT:                                      │
│ │ Thesis: T-12 (Long Duration) | Type: AUTO (agent-gen)  │
│ │ Signal conviction: 68% | Risk approval: AUTO            │
│ │ Submitted by: orchestrator | Time: 2026-05-23 14:30:21 │
│ │                                                         │
│ │ ORDER DETAILS:                                          │
│ │ Instrument: BND.US (iShares Aggregate Bond ETF)        │
│ │ Quantity: 2800 units | Notional: $283.4K               │
│ │ Order type: MARKET | Time in force: IOC (fill-or-kill) │
│ │ Limit price: N/A | Stop: N/A                           │
│ │                                                         │
│ │ EXECUTION:                                              │
│ │ Submitted: 14:30:21 UTC | Filled: 14:30:21.3 UTC       │
│ │ Fill qty: 2800 (100%) | Fill price avg: $101.23        │
│ │ Broker: PAPER_BROKER (simulated) | Commission: $0     │
│ │                                                         │
│ │ EXECUTION QUALITY ANALYSIS:                             │
│ │ VWAP at order time: $101.29                            │
│ │ Slippage: -0.6bps (outperformed VWAP) ✅               │
│ │ Reason: Low spread ($0.02), high volume (2.1M daily)  │
│ │                                                         │
│ │ COST BREAKDOWN:                                         │
│ │ Price: $283.4K                                         │
│ │ Commission: $0 (paper mode)                            │
│ │ Slippage: -$17 (favorable)                             │
│ │ Total cost: $283.4K                                    │
│ │                                                         │
│ │ [View fills] [View tape] [Audit trail] [Revert?]      │
│ └─────────────────────────────────────────────────────────┘
│
│ MANUAL ORDER ENTRY (below):
│ ┌─────────────────────────────────────────────────────────┐
│ │ SUBMIT MANUAL ORDER                                     │
│ │ Symbol: [BND.US__________] | Type: [MARKET ▼]          │
│ │ Side: [BUY ▼] | Qty: [_________] units                 │
│ │ Limit Price: [_______] | Time in force: [IOC ▼]       │
│ │ Reason/Notes: [_____________________________]           │
│ │ Linked thesis: [T-12 ▼] or [NONE]                      │
│ │                                                         │
│ │ ⚠️  Risk check: Notional = $283.4K (would breach...)   │
│ │    Not allowed without override.                        │
│ │ [Override & Submit] [Cancel]                           │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Real-time (orders appear instantly, fills within 1-2s)

**User actions available**:
- **Submit manual trade** (override agent with your own order)
- **Cancel pending order** (if still not filled)
- **Review execution quality** (slippage, VWAP comparison)
- **Adjust order** (modify limit price, quantity) [if pending]
- **View tape** (detailed fill breakdown for large orders)
- **Replay trade** (hypothetical: what if different size/price?)

---

### ⑥ AGENTS & RUNTIME

**Purpose**: Workforce orchestration. Agent health, task status, capability routing, LLM failover.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ AGENTS & RUNTIME                                            │
├─────────────────────────────────────────────────────────────┤
│
│ AGENT ROSTER:
│ ┌──────────┬────────────┬──────────┬───────────┬──────────┐
│ │ AGENT    │ ROLE       │ STATUS   │ TASKS     │ CPU/MEM  │
│ ├──────────┼────────────┼──────────┼───────────┼──────────┤
│ │ macro_1  │ Macro      │ 🟢 READY │ 2 active  │ 34%/127M │
│ │          │ analyst    │          │ (1 q'd)   │          │
│ ├──────────┼────────────┼──────────┼───────────┼──────────┤
│ │ tech_1   │ Technical  │ 🟢 READY │ 1 active  │ 28%/112M │
│ │          │ analyst    │          │ (0 q'd)   │          │
│ ├──────────┼────────────┼──────────┼───────────┼──────────┤
│ │ research │ Fundamental│ 🟢 READY │ 0 active  │ 18%/98M  │
│ │ _1       │ analyst    │          │ (0 q'd)   │          │
│ ├──────────┼────────────┼──────────┼───────────┼──────────┤
│ │ discovery│ Scout      │ 🟢 READY │ 3 active  │ 45%/156M │
│ │ _wave_1  │ orchestrator│          │ (5 q'd)   │          │
│ ├──────────┼────────────┼──────────┼───────────┼──────────┤
│ │ sentiment│ Sentiment  │ ⏳ BUSY  │ 2 active  │ 67%/201M │
│ │ _1       │ analyst    │ (48h     │ (2 q'd)   │ (HIGH)   │
│ │          │            │ running) │           │          │
│ ├──────────┼────────────┼──────────┼───────────┼──────────┤
│ │ approval │ CEO        │ 🟢 READY │ 1 pending │ 12%/64M  │
│ │ _center  │ (you)      │          │ from you  │          │
│ └──────────┴────────────┴──────────┴───────────┴──────────┘
│
│ ACTIVE TASKS (by agent):
│ ┌─────────────────────────────────────────────────────────┐
│ │ macro_1 (Macro Analyst):                                │
│ │  • Task M-121: "Fed pivot signal strength" (4.2h)      │
│ │    Status: IN_PROGRESS | Data sources: 5/5 ready      │
│ │    Output: Estimating signal conviction ██████░░░░░    │
│ │                                                         │
│ │  • Task M-120: "Yield curve inversion risk" (12.1h)    │
│ │    Status: COMPLETED | Result: 34% recession signal   │
│ │    Next: Waiting for discovery_wave_1 to use output   │
│ │                                                         │
│ │ discovery_wave_1 (Scout Orchestrator):                  │
│ │  • Task D-89: "Tech sector scan: AI capex" (2.1h)      │
│ │    Assigned to: tech_1, research_1 (subtasks)         │
│ │    Status: IN_PROGRESS | Hit count: 12 ideas so far   │
│ │    Est. time remaining: 1.8h                          │
│ │                                                         │
│ │  • Task D-88: "Energy transition: renewables" (18.2h)  │
│ │    Status: COMPLETED | Ideas generated: 7            │
│ │    Conviction avg: 54% | Linked to thesis: T-9, T-10 │
│ │                                                         │
│ │ sentiment_1 (Sentiment Analyzer):                       │
│ │  • Task S-45: "Fed speaker tone analysis" (ongoing)    │
│ │    Status: LONG_RUNNING (48h) | CPU HIGH (67%)        │
│ │    Processing: 234K articles/tweets (8.3% done)       │
│ │    Alert: May hit timeout in 12h, consider stopping   │
│ │    [Pause?] [Stop?] [Let it finish?]                  │
│ │                                                         │
│ │ approval_center:                                        │
│ │  • Pending decision from CEO:                          │
│ │    "Should we deploy additional $200K to T-12?"       │
│ │    Awaiting since: 2026-05-23 14:30 (1.2h pending)    │
│ │                                                         │
│ │ [View task details] [View logs] [View outputs]        │
│ └─────────────────────────────────────────────────────────┘
│
│ LLM ROUTING & HEALTH:
│ ┌─────────────────────────────────────────────────────────┐
│ │ VENDOR: Claude (Anthropic)                              │
│ │ Status: 🟢 HEALTHY | Uptime: 99.8%                     │
│ │ Last request: 2s ago | Queue: 3 / 10 slots used        │
│ │ Token budget: $450/month | Used: $127 (28%)            │
│ │ Rate limit: 50 req/min | Current: 8 req/min            │
│ │                                                         │
│ │ VENDOR: GPT-4 (OpenAI) [Fallback]                       │
│ │ Status: 🟡 DEGRADED | Uptime: 95.2%                    │
│ │ Last error: 12min ago (timeout on large context)       │
│ │ Queue: 2 / 10 slots used                               │
│ │ Token budget: $300/month | Used: $98 (33%)             │
│ │ Auto-routing: Disabled (prefer Claude)                 │
│ │                                                         │
│ │ VENDOR: Gemini (Google) [Fallback]                      │
│ │ Status: 🟢 READY | Uptime: 99.5%                       │
│ │ Never used in current rotation                         │
│ │ Available as fallback if Claude + GPT-4 fail           │
│ │                                                         │
│ │ [Manage vendors] [View costs] [Adjust routing]         │
│ └─────────────────────────────────────────────────────────┘
│
│ ORCHESTRATOR CONTROL:
│ ┌─────────────────────────────────────────────────────────┐
│ │ RUNTIME STATE: 🟢 RUNNING                               │
│ │ Last heartbeat: 0.3s ago | Uptime: 8d 12h 34min       │
│ │                                                         │
│ │ [Pause orchestration] [Resume] [Restart] [Reset]       │
│ │                                                         │
│ │ If you pause: agents stop, no new tasks, existing run  │
│ │ If you restart: clean agent state, fresh task queue    │
│ │ If you reset: full knowledge graph rebuild              │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Real-time (agent status streamed, task progress every 5s)

**User actions available**:
- **Pause/resume individual agent** (stop a runaway task)
- **Pause/resume entire orchestration** (freeze everything)
- **View agent logs** (see reasoning, data fetches, errors)
- **View task outputs** (what did agent generate?)
- **Restart agent** (reset its state if stuck)
- **Manage LLM routing** (prefer Claude, fallback to GPT-4, etc.)
- **Adjust agent task allocation** (give more work to fast agents)

---

### ⑦ APPROVALS & CEO DIGESTS

**Purpose**: CEO decision points. Things that need your input. Digests that tell the story of what happened.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ APPROVALS & CEO DIGESTS                                     │
├─────────────────────────────────────────────────────────────┤
│
│ PENDING APPROVALS (you must decide):
│ ┌─────────────────────────────────────────────────────────┐
│ │ [1] CAPITAL ALLOCATION: Deploy $200K to T-12?          │
│ │                                                         │
│ │ Thesis T-12 (Long Duration):                           │
│ │ • Current conviction: 68% ⬆️ (was 60% 5d ago)          │
│ │ • Current allocation: $400K | Max allowed: $500K       │
│ │ • Agent recommendation: "Increase to $600K for 2x ROI" │
│ │ • Your position size limit policy: Max 20% = $500K    │
│ │ • If approved: Will hit exactly at 20% limit           │
│ │                                                         │
│ │ [APPROVE] [APPROVE w/ NOTES] [REJECT] [ASK_AGENT]      │
│ │                                                         │
│ │ ────────────────────────────────────────────────────    │
│ │                                                         │
│ │ [2] NEW HYPOTHESIS: Create thesis from research R-46?  │
│ │                                                         │
│ │ Research R-46 (NVIDIA AI Capex Surge):                 │
│ │ • Conviction: 71% | Type: FUNDAMENTAL                  │
│ │ • Source: discovery_wave_1 + research_1                │
│ │ • Proposed allocation: $150K (initial) | Max: $300K    │
│ │ • Suggested positions: [NVDA, ASML, QCOM]             │
│ │ • Risk check: Already 25% Tech, this adds +2% more     │
│ │   (would be 27%, under 35% limit) ✅                   │
│ │                                                         │
│ │ [APPROVE THESIS] [MODIFY & APPROVE] [REJECT]           │
│ │                                                         │
│ │ ────────────────────────────────────────────────────    │
│ │                                                         │
│ │ [3] MANUAL TRADE: Buy 1000 shares of XYZ at $50?       │
│ │                                                         │
│ │ Order: XYZ $50K notional | Your threshold: $100K       │
│ │ Reason: "CEO discretionary entry, strong conviction"   │
│ │ Linked to thesis: None (discretionary)                 │
│ │ Risk review: OK, no sector/correlation issues         │
│ │                                                         │
│ │ [APPROVE] [APPROVE w/ NOTES] [REJECT]                  │
│ └─────────────────────────────────────────────────────────┘
│
│ APPROVAL HISTORY (last 30d):
│ ┌──────┬────────────────────────────────┬────────┬─────────┐
│ │ DATE │ DECISION                       │ RESULT │ OUTCOME │
│ ├──────┼────────────────────────────────┼────────┼─────────┤
│ │ 05-20│ Approve T-10 (Energy) $180K    │ ✅ YES │ +$7.4K  │
│ │ 05-18│ Reject R-42 (Energy storage)   │ ❌ NO  │ N/A     │
│ │ 05-15│ Approve T-11 (Tech rotation)   │ ✅ YES │ -$3.1K  │
│ │ 05-12│ Approve $50K to T-12           │ ✅ YES │ +$8.1K  │
│ └──────┴────────────────────────────────┴────────┴─────────┘
│
│ DAILY CEO DIGEST (auto-generated summary):
│ ┌─────────────────────────────────────────────────────────┐
│ │ FUND DIGEST: 2026-05-23                                │
│ │                                                         │
│ │ TODAY IN NUMBERS:                                       │
│ │ • PnL: +$3,200 (+0.13% daily) | YTD: +$87,400 (+3.5%) │
│ │ • Exposure: 68% deployed | Sharpe: 1.24               │
│ │ • 3 trades executed, 0 errors | Approval rate: 100%    │
│ │                                                         │
│ │ ACTIVE THESES SNAPSHOT:                                 │
│ │ • T-12 (Long Duration): $400K, +$18.2K, conviction 68% │
│ │ • T-11 (Tech rotation): $200K, -$3.1K, conviction 54%  │
│ │ • T-10 (Energy): $180K, +$7.4K, conviction 41%         │
│ │ • T-9 (Other): $150K, +$3.1K, conviction 38%           │
│ │                                                         │
│ │ KEY DECISIONS MADE:                                     │
│ │ ✅ Approved $180K to T-10 (energy transition)          │
│ │ ✅ Executed 3 orders (all at good fills)               │
│ │ ⏳ Pending: 1 allocation decision, 2 new thesis approvals
│ │                                                         │
│ │ MARKET CONTEXT:                                         │
│ │ • Fed speakers: Dovish tone (3/4 speakers)             │
│ │ • VIX: 18.2 (down 0.8d-o-d)                            │
│ │ • 10Y yield: 4.21% (up 2bps)                           │
│ │ • Macro score: Growth up, inflation steady              │
│ │                                                         │
│ │ AGENTS WORKING ON:                                      │
│ │ • macro_1: Fed pivot signal (4.2h, ██████░░░░░)        │
│ │ • discovery_wave_1: Tech AI capex (2.1h, ████░░░░░░░░) │
│ │ • sentiment_1: Long-running analysis (47.8h elapsed)   │
│ │                                                         │
│ │ RISK STATUS: ✅ ALL GREEN                              │
│ │ • VaR: $28.4K (65% margin to limit)                    │
│ │ • Max DD: -3.2% (75% margin to limit)                  │
│ │ • Leverage: 1.2x (20% margin to limit)                 │
│ │                                                         │
│ │ THINGS TO REVIEW:                                       │
│ │ 1. sentiment_1 has been running 48h; consider stopping  │
│ │ 2. T-11 conviction dropped 2% WoW; watch exit signal    │
│ │ 3. New research R-46 (NVIDIA) looks high conviction     │
│ │                                                         │
│ │ [View full digest] [Export] [Email to stakeholders]    │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Approvals appear in real-time as agents request them. Digests generated daily at 18:00 UTC.

**User actions available**:
- **Approve/reject** pending decisions
- **Approve with notes** (record your reasoning)
- **Revisit past decisions** (see why you approved/rejected each one)
- **Export digest** (share with stakeholders, investors)
- **Schedule digests** (daily, weekly, monthly)

---

### ⑧ AUDIT & LINEAGE

**Purpose**: Complete decision history. Trace any trade back to its origins.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ AUDIT & LINEAGE                                             │
├─────────────────────────────────────────────────────────────┤
│
│ DECISION SEARCH:
│ Type: [ALL] [THESIS_CREATION] [TRADE] [APPROVAL] [SIGNAL_UPDATE]
│ Date range: [TODAY] [THIS WEEK] [THIS MONTH] [CUSTOM]
│ Status: [ALL] [APPROVED] [REJECTED] [EXECUTED] [PENDING]
│
│ DECISION LOG TABLE:
│ ┌────────┬────────────────────┬──────────┬───────────┬────────┐
│ │ DATE   │ DECISION           │ TYPE     │ STATUS    │ DETAIL │
│ ├────────┼────────────────────┼──────────┼───────────┼────────┤
│ │ 05-23  │ Execute order O-89 │ TRADE    │ ✅ FILLED │ [+]    │
│ │ 14:30  │ (BND.US, $283K)    │          │           │        │
│ ├────────┼────────────────────┼──────────┼───────────┼────────┤
│ │ 05-23  │ Approve allocation │ APPROVAL │ ✅ APPROVE│ [+]    │
│ │ 14:15  │ $400K to T-12      │          │           │        │
│ ├────────┼────────────────────┼──────────┼───────────┼────────┤
│ │ 05-23  │ Create thesis T-12 │ THESIS   │ ✅ ACTIVE │ [+]    │
│ │ 10:30  │ (Long Duration)    │          │           │        │
│ ├────────┼────────────────────┼──────────┼───────────┼────────┤
│ │ 05-20  │ Fed pivot signal   │ SIGNAL   │ ✅ ACTIVE │ [+]    │
│ │ 16:45  │ updated +8%        │ UPDATE   │           │        │
│ └────────┴────────────────────┴──────────┴───────────┴────────┘
│
│ DECISION LINEAGE (click [+] to expand):
│ ┌─────────────────────────────────────────────────────────┐
│ │ DECISION: Execute order O-89 (BND.US Long, $283.4K)    │
│ │ Decision ID: dec_2026052314301847 | Timestamp: 14:30   │
│ │                                                         │
│ │ LINEAGE CHAIN:                                          │
│ │                                                         │
│ │ [LEVEL 1] Market data trigger                           │
│ │ └─ CPI data released: 0.2% below expectations           │
│ │    • Source: US Bureau of Labor Statistics              │
│ │    • Confidence: High (official release)                │
│ │    • Time: 2026-05-22 13:30 UTC                         │
│ │                                                         │
│ │ [LEVEL 2] Signal update                                 │
│ │ └─ Fed pivot signal R-47 conviction: 60% → 68%         │
│ │    • Agent: macro_1 (macro analyst)                     │
│ │    • Input data: [CPI, fed_funds, media_tone]           │
│ │    • Model: Fed pivot XGBoost classifier                │
│ │    • Confidence: 71% (model output)                     │
│ │    • Time: 2026-05-22 14:15 UTC                         │
│ │    • SHAP analysis: [show feature importance]           │
│ │                                                         │
│ │ [LEVEL 3] Thesis decision                               │
│ │ └─ Create thesis T-12 (Long Duration)                   │
│ │    • Based on: R-47 (Fed pivot research)                │
│ │    • Initial conviction: 68%                            │
│ │    • Recommended allocation: $300K–$500K                │
│ │    • Agent recommendation created by: discovery_wave_1  │
│ │    • Time: 2026-05-23 10:30 UTC                         │
│ │                                                         │
│ │ [LEVEL 4] Approval decision                             │
│ │ └─ CEO approves thesis T-12 allocation: $400K           │
│ │    • Approved by: CEO (you)                             │
│ │    • Notes: "Strong conviction, fits duration play"     │
│ │    • Time: 2026-05-23 14:15 UTC                         │
│ │                                                         │
│ │ [LEVEL 5] Execution decision                            │
│ │ └─ Orchestrator creates trade O-89: BND.US $283.4K      │
│ │    • Generated by: fund_orchestrator                    │
│ │    • Risk gate: PASSED (policy check)                   │
│ │    • Linked to thesis: T-12 (auto-link)                 │
│ │    • Time: 2026-05-23 14:30:15 UTC                      │
│ │                                                         │
│ │ [LEVEL 6] Execution outcome                             │
│ │ └─ Order filled: 2800 units @ $101.23 avg               │
│ │    • Broker: paper_broker (simulated)                   │
│ │    • Fill quality: -0.6bps vs VWAP (favorable)         │
│ │    • Time: 2026-05-23 14:30:21 UTC                      │
│ │    • Notional: $283.4K                                  │
│ │    • Commission: $0                                     │
│ │                                                         │
│ │ OUTCOME (so far):                                        │
│ │ • Entry: 2026-05-23 @ $101.23                           │
│ │ • Current: $103.18 (2 days later)                       │
│ │ • Unrealized PnL: +$5,460 (+1.9%)                       │
│ │ • Status: OPEN (linked to thesis T-12)                  │
│ │                                                         │
│ │ [View all levels] [Export lineage] [Audit trail]       │
│ │ [Re-analyze decision] [View risk gate log]              │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Updated in real-time as decisions are made.

**User actions available**:
- **Trace any trade** (see full decision chain)
- **View risk gate decision** (what constraints were checked?)
- **View agent reasoning** (SHAP, model outputs, confidence)
- **Export lineage** (for compliance, audits, post-mortem)
- **Re-analyze decision** (what if different signal? different conviction?)

---

### ⑨ MARKET CONTEXT

**Purpose**: Macro regime + market state. Informs all signal weighting + model routing.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ MARKET CONTEXT                                              │
├─────────────────────────────────────────────────────────────┤
│
│ REGIME CLASSIFICATION:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Current Regime: RISK_ON_GROWTH                          │
│ │ Confidence: 78% | Updated: 2026-05-23 14:30 UTC         │
│ │ Duration in regime: 8 days | Historical avg: 12 days   │
│ │                                                         │
│ │ Regime probabilities:                                    │
│ │   ├─ RISK_ON_GROWTH: 78% [████████████████░]           │
│ │   ├─ RISK_OFF_FLIGHT: 15% [███░░░░░░░░░░░░░]           │
│ │   ├─ STAGFLATION: 5% [█░░░░░░░░░░░░░░░░░░]             │
│ │   └─ VOLATILE_CHOP: 2% [░░░░░░░░░░░░░░░░░░]            │
│ │                                                         │
│ │ Last regime switch: 2026-05-15 (8 days ago)            │
│ │ → FROM: RISK_OFF_FLIGHT (inflation cooling)            │
│ │ → TO: RISK_ON_GROWTH (Fed pause priced in)             │
│ └─────────────────────────────────────────────────────────┘
│
│ MACRO FACTOR SNAPSHOT:
│ ┌──────────────────────────────────────────────────────────┐
│ │ GROWTH INDICATORS:                                       │
│ │ US GDP nowcast (Atlanta Fed): 2.3% | Trend: +0.4 WoW   │
│ │ ISM Manufacturing PMI: 52.1 | Status: EXPANSION         │
│ │ Job creation (30d avg): 189K/month | Trend: Steady      │
│ │ Earnings revisions (S&P 500): +0.8% YoY | Momentum: Up  │
│ │                                                         │
│ │ INFLATION INDICATORS:                                    │
│ │ CPI (headline): 3.2% YoY | Trend: -0.3 YoY             │
│ │ Core CPI: 3.8% YoY | Trend: -0.2 YoY                   │
│ │ Fed expectations: 2.5% by Dec 2026 | Confidence: High  │
│ │ Market inflation breakevens: 2.3% (5Y, real-time)      │
│ │                                                         │
│ │ MONETARY POLICY:                                         │
│ │ Fed Funds Rate: 5.25%–5.50% | Trend: Paused (hold)     │
│ │ Probability of cut by Q3: 75% | Market-implied cuts: 2 │
│ │ QT status: $60B/month runoff | Trend: Ongoing           │
│ │                                                         │
│ │ SENTIMENT / RISK INDICATORS:                             │
│ │ VIX (realized vol proxy): 18.2 | 30d avg: 16.8         │
│ │ Put/call ratio: 0.78 (slightly bullish)                │
│ │ Credit spreads (IG OAS): 98bps | Trend: Tightening     │
│ │ Term premium (10Y–2Y): 1.8% | Status: Normal           │
│ │                                                         │
│ │ CURRENCY / COMMODITIES:                                  │
│ │ USD Index: 103.4 | 30d trend: +1.2% (strong)           │
│ │ Oil (WTI): $82/bbl | Trend: Steady (supply concerns)   │
│ │ Gold: $2,042/oz | Trend: Down 2% (risk-on rotations)   │
│ │ BTC: $42,300 | Trend: Up 8% WoW (risk appetite)        │
│ └──────────────────────────────────────────────────────────┘
│
│ MARKET REGIME IMPLICATIONS FOR SIGNALS:
│ ┌─────────────────────────────────────────────────────────┐
│ │ In RISK_ON_GROWTH regime:                               │
│ │ ✅ Favor: Cyclicals, growth, risk assets                │
│ │ ✅ Tech + Financials outperform                         │
│ │ ✅ Volatility models shift to momentum-driven           │
│ │ ⚠️  Avoid: Duration, defensive, bonds (except short)   │
│ │                                                         │
│ │ Model routing for this regime:                          │
│ │ • Technical: Use momentum classifier (not mean revert)  │
│ │ • Fundamental: Weight growth factors (not value)        │
│ │ • Sentiment: Higher weight (crowdsourced alpha works)   │
│ │ • Risk: Reduce hedges, allow higher leverage            │
│ │                                                         │
│ │ Your T-12 thesis (Long Duration) in this regime:        │
│ │ ⚠️  REGIME MISMATCH: Bonds underperform in growth phase │
│ │    Conviction may be too high for current regime        │
│ │    → Consider rebalancing? Reduce allocation? [+]       │
│ └─────────────────────────────────────────────────────────┘
│
│ ECONOMIC CALENDAR (next 7 days):
│ ┌──────┬────────────────────────────┬─────────┬────────────┐
│ │ DATE │ EVENT                      │ TIME    │ IMPORTANCE │
│ ├──────┼────────────────────────────┼─────────┼────────────┤
│ │ 05-24│ Initial jobless claims     │ 12:30   │ 🔴 HIGH   │
│ │ 05-28│ GDP (advance estimate)     │ 12:30   │ 🔴 HIGH   │
│ │ 05-29│ PCE inflation (core)       │ 12:30   │ 🔴 HIGH   │
│ │ 05-30│ Fed Chair testimony (Senate)│ 10:00   │ 🔴 HIGH   │
│ └──────┴────────────────────────────┴─────────┴────────────┘
│
│ [View macro model] [View regime history] [View calendar]
│ [Alert on regime switch] [Adjust model weights for regime]
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Real-time for market prices, daily for macro nowcasts.

**User actions available**:
- **View macro regime history** (when did switches happen? why?)
- **Adjust model routing** (if you disagree with regime call)
- **Set alerts** (notify me if regime switches)
- **Review regime implications** (how does this affect my theses?)

---

### ⑩ SETTINGS & CONFIGURATION

**Purpose**: System tuning. Risk limits, approval thresholds, agent allocation, LLM routing, UI preferences.

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ SETTINGS & CONFIGURATION                                    │
├─────────────────────────────────────────────────────────────┤
│
│ RISK LIMITS:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Max VaR (daily, 95%): $50K           [Current: $28.4K] │
│ │ Max Drawdown: -15%                   [Current: -3.2%]  │
│ │ Max Leverage (gross): 1.5x            [Current: 1.2x]  │
│ │ Max position size: 8%                 [Current max: 6.2%]│
│ │ Max sector concentration: 40%         [Current: 31%]   │
│ │ Min correlation score: 0.8            [Current avg: 0.82]│
│ │                                                         │
│ │ [Reset to defaults] [Import from file] [Export]        │
│ └─────────────────────────────────────────────────────────┘
│
│ APPROVAL THRESHOLDS:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Manual trades > $ amount require CEO approval:          │
│ │ Single order: [$100K ▼] (currently $100K)              │
│ │ Daily cumulative: [$250K ▼]                            │
│ │ New thesis allocation: [$150K ▼]                       │
│ │ Conviction override (vs signal): [±20% ▼]             │
│ │                                                         │
│ │ Auto-approve (no CEO required):                         │
│ │ ☑️ Trades linked to active thesis                       │
│ │ ☑️ Rebalance trades within thesis                       │
│ │ ☑️ Stop-loss orders (auto-triggered)                    │
│ │ ☐ Discretionary new theses < $50K                      │
│ │                                                         │
│ │ [Save] [Reset to defaults]                             │
│ └─────────────────────────────────────────────────────────┘
│
│ AGENT ALLOCATION:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Discovery frequency: [Every 1h ▼]                       │
│ │ Max concurrent discovery tasks: [3 ▼]                  │
│ │ Macro scan: [Daily ▼]                                  │
│ │ Sentiment analysis: [Continuous ▼] (⚠️ resource heavy) │
│ │ Research retraining: [Weekly ▼]                        │
│ │                                                         │
│ │ Agent autopilot: [ON ▼] (auto-create theses if conv>60%)
│ │ Autopilot creation threshold: [60% ▼]                  │
│ │ Autopilot allocation limit: [$100K ▼] per thesis      │
│ │                                                         │
│ │ [Apply] [Preview impact] [Reset]                       │
│ └─────────────────────────────────────────────────────────┘
│
│ LLM ROUTING & COSTS:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Primary LLM vendor: [Claude (Anthropic) ▼]              │
│ │ Fallback vendor: [GPT-4 (OpenAI) ▼]                     │
│ │ 3rd fallback: [Gemini (Google) ▼]                       │
│ │                                                         │
│ │ Budget caps (monthly):                                  │
│ │ Claude: [$500 ▼] | Current: $127 (28%)                │
│ │ GPT-4: [$300 ▼] | Current: $98 (33%)                  │
│ │ Gemini: [$100 ▼] | Current: $0 (0%)                   │
│ │                                                         │
│ │ Auto-stop when budget reached: [ON ▼]                   │
│ │ Send alert at 80% of budget: [ON ▼]                     │
│ │                                                         │
│ │ [View cost history] [Optimize vendor routing]          │
│ └─────────────────────────────────────────────────────────┘
│
│ UI & NOTIFICATIONS:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Theme: [Dark ▼] | Font size: [Medium ▼]                │
│ │                                                         │
│ │ Alert notifications:                                    │
│ │ ☑️ Critical (risk limit breached)                       │
│ │ ☑️ Approvals pending (in-app badge + email)             │
│ │ ☑️ Large trades (> $100K filled)                        │
│ │ ☑️ Macro events (high-importance calendar events)       │
│ │ ☐ Routine agent task completions                       │
│ │                                                         │
│ │ Digest frequency: [Daily @ 18:00 UTC ▼]                │
│ │ Digest channels: [In-app ▼] [Email ▼] [Slack ▼]        │
│ │                                                         │
│ │ [Test notification] [Manage subscriptions]              │
│ └─────────────────────────────────────────────────────────┘
│
│ OPERATIONAL SETTINGS:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Trading hours: [US market 09:30–16:00 EST ▼]           │
│ │ Pre-market trading: [OFF ▼]                             │
│ │ After-hours trading: [OFF ▼]                            │
│ │ Weekend/holiday trading: [OFF ▼]                        │
│ │                                                         │
│ │ Paper mode: [ON] (no live execution)                    │
│ │   • When switching to LIVE: [Not yet available]        │
│ │   • Live trading requires: Manual migration + testing   │
│ │                                                         │
│ │ Data refresh rate (UI): [Real-time ▼]                   │
│ │ Historical data update (daily): [02:00 UTC ▼]          │
│ │                                                         │
│ │ [Save all changes]                                      │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Configuration changes apply immediately to runtime.

**User actions available**:
- **Adjust any risk limit** (immediate effect)
- **Adjust approval thresholds** (change what requires your sign-off)
- **Tune agent allocation** (more/less discovery, change frequency)
- **Manage LLM budgets** (control costs, set fallbacks)
- **Enable/disable features** (autopilot, pre-market, etc.)

---

### ⑪ KNOWLEDGE GRAPH & MEMORY

**Purpose**: Fund memory. What have we learned? What patterns are we tracking? What is the knowledge base?

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ KNOWLEDGE GRAPH & MEMORY                                    │
├─────────────────────────────────────────────────────────────┤
│
│ KNOWLEDGE STATS:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Total decisions logged: 847 | Approved: 821 | Rejected: 26
│ │ Total theses created: 34 | Active: 7 | Closed: 27     │
│ │ Total trades executed: 412 | Avg P&L: +1.2%           │
│ │ Total signals generated: 18,234 | High confidence: 4,821
│ │ Research ideas discovered: 156 | Converted to thesis: 34
│ │ Learning loops completed: 23 (monthly retraining)      │
│ │                                                         │
│ │ Knowledge graph size: 2.3GB | Backup: ON (daily)      │
│ └─────────────────────────────────────────────────────────┘
│
│ RECENT MEMORY QUERIES:
│ ┌──────────────────────────────────────────────────────────┐
│ │ Q: "What theses have worked best?"                       │
│ │ A: Top 3 by Sharpe ratio:                               │
│ │    • T-1 (Energy transition): 2.4 Sharpe, +$125K       │
│ │    • T-3 (Fed shorts): 1.9 Sharpe, +$89K               │
│ │    • T-5 (Tech AI capex): 1.6 Sharpe, +$67K            │
│ │                                                         │
│ │ Q: "When did we last see this signal pattern?"         │
│ │ A: Similar Fed pivot + CPI decline pattern seen:       │
│ │    • 2024-12 (resulted in +2.1% thesis return)         │
│ │    • 2023-07 (resulted in +1.8% thesis return)         │
│ │    • Average outcome: +1.9% return, 8d holding period  │
│ │                                                         │
│ │ Q: "What macros lead to sector rotation?"              │
│ │ A: Top correlations to rotation signals:               │
│ │    • Fed rate expectations: 0.76 correlation           │
│ │    • VIX > 20: 0.68 correlation                        │
│ │    • Credit spreads widening: 0.61 correlation         │
│ │                                                         │
│ │ [Ask custom question] [View all memory]                │
│ └──────────────────────────────────────────────────────────┘
│
│ DECISION PATTERNS:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Approval bias analysis:                                 │
│ │ • You approve: 97.1% of agent recommendations          │
│ │   (above typical: 70%)                                  │
│ │   → Interpretation: Agents are well-calibrated for you │
│ │                                                         │
│ │ • Avg approval size: $310K                              │
│ │ • Avg rejection size: $127K (you reject smaller bets)  │
│ │   → Pattern: You have conviction on bigger ideas       │
│ │                                                         │
│ │ • Approval time: Median 18 minutes (pretty responsive) │
│ │                                                         │
│ │ Win rate by type:                                       │
│ │ • Macro theses: 64% positive outcome | Avg return: +1.8%│
│ │ • Fundamental theses: 71% | Avg return: +2.1%          │
│ │ • Technical theses: 52% | Avg return: +0.9%            │
│ │ → You're better at fundamental + macro than technical  │
│ │                                                         │
│ │ [View detailed bias analysis] [Export insights]        │
│ └─────────────────────────────────────────────────────────┘
│
│ SIGNAL PERFORMANCE MEMORY:
│ ┌─────────────────────────────────────────────────────────┐
│ │ Best-performing signals (by hit rate):                  │
│ │ 1. Fed pivot signal (R-47): 68% win rate               │
│ │ 2. Earnings revisions (R-12): 61% win rate             │
│ │ 3. Sentiment divergence (S-4): 58% win rate            │
│ │                                                         │
│ │ Worst-performing:                                       │
│ │ 1. Pure technical momentum (T-34): 31% win rate        │
│ │ 2. Volatility mean reversion (T-12): 34% win rate      │
│ │ 3. Social sentiment (S-2): 39% win rate                │
│ │                                                         │
│ │ → Recommendation: Deweight technical, boost fundamental│
│ │                                                         │
│ │ [View detailed signal audit] [Update model weights]    │
│ └─────────────────────────────────────────────────────────┘
│
│ FUND NARRATIVE:
│ Auto-generated narrative about your fund's journey:
│ ┌─────────────────────────────────────────────────────────┐
│ │ VEKTOR FUND HISTORY (generated narrative)              │
│ │                                                         │
│ │ Your fund started 8 months ago with $2.5M AUM. Over   │
│ │ the period, you've generated +$117.4K in PnL (4.7%),   │
│ │ with a 1.24 Sharpe and -3.2% max drawdown. You've     │
│ │ created 34 theses across macro, fundamental, and       │
│ │ technical domains, with 100% of them profitable on     │
│ │ paper.                                                  │
│ │                                                         │
│ │ Your strongest domain is fundamental analysis (71% hit  │
│ │ rate), where you've captured value rotations and       │
│ │ earnings surprises. Macro theses have also worked well │
│ │ (64% hit rate), particularly around Fed policy shifts. │
│ │                                                         │
│ │ You tend to approve larger bets and reject smaller     │
│ │ ones, suggesting you have strong conviction on key     │
│ │ ideas. Your approval lag is 18 minutes, indicating      │
│ │ responsive CEO oversight.                              │
│ │                                                         │
│ │ Your agent workforce has discovered 156 research ideas │
│ │ (34 converted to live theses), with macro and          │
│ │ fundamental scouts being most reliable. Your LLM       │
│ │ orchestration has been stable, with 99.8% uptime on    │
│ │ Claude and no budget overruns.                         │
│ │                                                         │
│ │ Looking ahead: Watch for regime shift signals. Your    │
│ │ T-12 (duration play) is regime-sensitive; consider     │
│ │ tightening stops if risk-on extends.                   │
│ │                                                         │
│ │ [Generate new narrative] [Share narrative]             │
│ └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Data updates**: Memory queries computed in real-time, narrative regenerated weekly.

**User actions available**:
- **Ask custom questions** (what patterns do you see?)
- **View signal performance** (which indicators work best?)
- **View decision bias** (are you over/under-weighting certain types?)
- **Export insights** (for team discussion, decision-making)

---

## Part 4: UI/UX Design Principles

### 4.1 Design Tenets for Vektor Admin

**Not a dashboard. A control center.**

1. **Information Hierarchy**: CEO decisions first, analytics second
   - Top priority: What needs my decision? What's broken? What's the status?
   - Secondary: Why did something happen? What's the pattern?
   - Tertiary: Historical analysis, optimizations, insights

2. **Real-time operative details**
   - NAV, positions, PnL update instantly
   - Risk metrics update on every trade
   - Agent task progress streams live
   - Alerts surface immediately (no polling)

3. **Drill-down over breadth**
   - Summary first (KPI tiles)
   - Click to expand detail (DECISION LINEAGE, not pre-expanded)
   - Avoid information overload with deep hierarchy
   - Every panel should answer one question

4. **Actionable alerts**
   - No vanity metrics or empty charts
   - Alerts = decisions needed or problems
   - Each alert has a recommended action

5. **Institutional design** (not fintech-flashy)
   - Dark theme (reduce eye strain for 8+ hour days)
   - Clean sans-serif fonts (system fonts: Inter, Roboto)
   - Consistent spacing + typography
   - Minimal animation (no bouncing, no bloat)
   - High contrast (accessibility)

6. **Traceability everywhere**
   - Every number links to its source
   - Every decision traces to inputs
   - Every action is logged with timestamp + user
   - No "black box" outputs

---

### 4.2 Layout Template

All panels follow this structure:

```
┌─────────────────────────────────────────────────────────────────┐
│ PANEL TITLE                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ FILTER/SEARCH BAR (if applicable)                              │
│ [Filter 1] [Filter 2] [Sort by] [Search____] [Export] [Refresh]│
│                                                                 │
│ SUMMARY ROW (high-level KPIs)                                  │
│ • Stat 1: X | Stat 2: Y | Stat 3: Z | Alert count: N         │
│                                                                 │
│ PRIMARY TABLE / CHART (sortable, clickable)                    │
│ ┌──────┬────────┬────────┬────────┬────────┬───────────────────┐
│ │ COL1 │ COL2   │ COL3   │ COL4   │ COL5   │ ACTION            │
│ ├──────┼────────┼────────┼────────┼────────┼───────────────────┤
│ │ ...  │ ...    │ ...    │ ...    │ ...    │ [Details▼]       │
│ └──────┴────────┴────────┴────────┴────────┴───────────────────┘
│                                                                 │
│ DETAIL PANEL (expands on click)                                │
│ ┌─────────────────────────────────────────────────────────────┐
│ │ Detailed info for selected row                              │
│ │ [Actions] [View history] [Export]                            │
│ └─────────────────────────────────────────────────────────────┘
│                                                                 │
│ FOOTER (pagination, record count, export)                      │
│ Records: 1–20 of 847 | [< PREV] [NEXT >] [Export all]         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Technology Stack Recommendation

### 5.1 Frontend

- **Framework**: React 18 (SPA, proven at scale)
- **State Management**: TanStack Query (server state) + Zustand (UI state)
- **UI Components**: Custom + Tailwind CSS (not Material-UI, too heavy)
- **Charts**: Recharts (simple, lightweight)
- **Real-time**: WebSocket (native fetch API for long-polling fallback)
- **Tables**: TanStack Table (headless, powerful, lightweight)
- **Routing**: React Router v6
- **HTTP**: Axios with interceptors for auth + error handling

**Why this stack?**
- Fast page loads (React is still king for SPAs)
- TanStack ecosystem is industry-standard + battle-tested
- Tailwind = fast UI iteration without bloat
- Recharts = good enough for institutional dashboards (not fancy)
- Real-time via WebSocket = smooth + responsive

### 5.2 Backend API

- **Framework**: FastAPI (Python, async, type-safe)
- **Real-time**: Server-sent events (SSE) or WebSocket via Starlette
- **Database**: PostgreSQL for decision ledger + knowledge graph
- **Caching**: Redis for hot data (NAV, positions, recent decisions)
- **Authentication**: JWT tokens with refresh logic
- **Rate limiting**: Per-user, per-endpoint
- **Logging**: Structured logging (JSON) to ELK

**Why?**
- FastAPI = fast iteration + built-in OpenAPI docs
- SSE = simpler than full WebSocket for 1-way streams
- PostgreSQL = ACID guarantees for decision logging
- Redis = instant cache hits for real-time metrics

### 5.3 Deployment

- **Frontend**: Vercel or Netlify (auto-deploy on git push)
- **Backend**: AWS ECS + Fargate (scale without managing servers) or DigitalOcean Kubernetes
- **Database**: AWS RDS PostgreSQL (managed, automated backups)
- **Cache**: AWS ElastiCache Redis
- **CDN**: CloudFront for static assets
- **Monitoring**: DataDog or New Relic for observability

---

## Part 6: Phased Rollout Plan

### Phase 1 (Weeks 1–4): MVP Control Center
- [x] Overview panel (fund status at a glance)
- [x] Research & Discovery (track ideas)
- [x] Theses & Positions (track bets)
- [ ] Risk & Policy (real-time constraint monitoring)
- [ ] Execution & Orders (trade lifecycle)

### Phase 2 (Weeks 5–8): Workforce + Audit
- [ ] Agents & Runtime (agent status, task management)
- [ ] Approvals & CEO Digests (approval workflows, daily narratives)
- [ ] Audit & Lineage (full decision traceability)
- [ ] Market Context (regime classification, macro state)

### Phase 3 (Weeks 9–12): Settings + Advanced
- [ ] Settings & Configuration (tune all parameters)
- [ ] Knowledge Graph & Memory (fund memory, pattern detection)
- [ ] Advanced features (stress tests, scenario planning, RL explainability)

### Phase 4 (Weeks 13+): Hardening + Optimization
- [ ] Performance tuning (WebSocket optimization, caching)
- [ ] Mobile responsiveness (work from phone)
- [ ] Integration with external dashboards (Tableau, etc.)
- [ ] Stakeholder portal (investor-facing views of public PnL + reports)

---

## Part 7: Success Criteria

### For CEO/Fund Manager:
- Can see entire fund state in <5 seconds (Overview)
- Can approve/reject decisions in <30 seconds (Approvals)
- Can drill to any trade's full lineage (Audit & Lineage)
- Can adjust risk limits without code changes (Settings)
- Can monitor agent workforce without logs (Agents & Runtime)

### For Engineering Team:
- Deployment time: <2 minutes (git push to live)
- API response time p99: <200ms
- WebSocket latency p99: <100ms
- Database query p99: <50ms (for cached queries)
- Uptime: >99.5% (excluding planned maintenance)

### For Operators:
- Discover fraud / bugs within 1 minute (alerts)
- Roll back any decision with full audit trail (lineage export)
- Share fund narrative with investors (auto-generated summaries)
- Train new team members using the system as source of truth (documentation via app)

---

## Conclusion

The **Vektor Admin Control Center** is not a dashboard. It is the **operating system of your fund**. Every panel enables a real CEO decision. Every piece of data is traceable to its source. Every action is logged and auditable.

This specification defines what you need to build and why. Your engineering team can use it to scope work, estimate timelines, and make architectural decisions.

**Next step**: Hand this spec to your coding agent. It has everything needed to build the complete system.

---

**Document Version**: 2.0  
**Last Updated**: 2026-05-23  
**Status**: Ready for implementation  

