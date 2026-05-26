# Vektor Admin Control Center
## Features Specification & Implementation Checklist

**Version**: 1.0  
**Date**: 2026-05-23  
**Purpose**: Complete feature breakdown for engineering team

---

## Master Feature List

Total features: 127 core features across 11 panels

---

## Panel 1: OVERVIEW (16 features)

### Real-Time KPIs
- [ ] **NAV Display** - Current fund NAV with previous NAV comparison
  - Inputs: nav_current, nav_previous, nav_inception
  - Outputs: NAV tile with % change, trend indicator
  - Update frequency: Real-time (on every trade)
  - API endpoint: `/admin/api/fund/nav`

- [ ] **Monthly PnL** - Month-to-date P&L in dollars and percent
  - vs benchmark comparison
  - vs monthly target if set
  - Update frequency: Real-time
  - API: `/admin/api/fund/monthly-pnl`

- [ ] **Sharpe Ratio** - Rolling 30-day Sharpe with historical trend
  - 30d avg, 90d avg, YTD
  - Color-coded: green if > 1.0, yellow if 0.5–1.0, red if < 0.5
  - Update frequency: Daily (end of day recalc)
  - API: `/admin/api/fund/sharpe`

- [ ] **Max Drawdown** - Current drawdown from high water mark
  - HWM date, current date, drawdown %
  - Margin to policy limit
  - Update frequency: Real-time on trades, historical daily
  - API: `/admin/api/fund/drawdown`

### Status Indicators
- [ ] **Runtime Status** - One-line summary of orchestrator health
  - Green = HEALTHY, Yellow = DEGRADED, Red = DOWN
  - Subcomponents: Orchestrator, Data pipeline, ML models, Broker, Agents
  - Click to drill into Agents & Runtime panel
  - Update frequency: Real-time heartbeat (every 5s)
  - API: `/admin/api/runtime/status`

- [ ] **Portfolio Exposure** - Deployment %, breakdown by asset class
  - Equities: $X (% of AUM)
  - Cash: $X (% of AUM)
  - Shorts: $X
  - Long/Short ratio
  - Gross leverage (vs limit)
  - Update frequency: Real-time on trades
  - API: `/admin/api/portfolio/exposure`

- [ ] **Risk Status** - One-line summary of risk metrics
  - VaR: $X (margin to limit: Y%)
  - Max DD: -X% (margin to limit: Y%)
  - Sector concentration: X% (limit: Y%)
  - Update frequency: Real-time
  - API: `/admin/api/risk/status`

### Alerts & Actions
- [ ] **Pending Alerts** - Count of critical alerts
  - Types: Approvals pending, Risk warnings, Data issues, Agent errors
  - Click to jump to relevant panel
  - Update frequency: Real-time on event
  - API: `/admin/api/alerts/pending`

- [ ] **Quick Action Buttons**
  - [View Full P&L] → jumps to PnL detail panel
  - [View Holdings] → jumps to Positions panel
  - [Approve Pending] → jumps to Approvals panel
  - [Control Center] → collapses summary, shows full admin UI
  - Styling: Secondary buttons, visible when on overview

---

## Panel 2: RESEARCH & DISCOVERY (18 features)

### Search & Filter
- [ ] **Filter by Status** - Dropdown: ALL, ACTIVE, ARCHIVED, REJECTED
  - Default: ALL
  - Updates table in real-time
  - API: `/admin/api/research/ideas?status=ACTIVE`

- [ ] **Filter by Type** - Dropdown: ALL, MACRO, SECTOR, FUNDAMENTAL, TECHNICAL, EVENT
  - Default: ALL
  - Multi-select optional
  - API: `/admin/api/research/ideas?type=MACRO,SECTOR`

- [ ] **Filter by Conviction** - Dropdown: ALL, HIGH (>60%), MEDIUM (40-60%), LOW (<40%)
  - Default: ALL
  - Color-coded badges
  - API: `/admin/api/research/ideas?conviction_min=60`

- [ ] **Filter by Source** - Dropdown: ALL, AGENT_DISCOVERY, CEO_INPUT, MARKET_SCAN
  - Default: ALL
  - API: `/admin/api/research/ideas?source=AGENT_DISCOVERY`

- [ ] **Search by Keyword** - Text input, searches title + description
  - Real-time filtering (debounced 300ms)
  - API: `/admin/api/research/ideas?search=Fed+pivot`

### Idea Management
- [ ] **Ideas List Table** - Sortable table with columns:
  - ID | TITLE | TYPE | CONVICTION (%) | DAYS LIVE | STATUS
  - Sortable by: ID, conviction (desc), days_live (desc), status
  - Clickable row expands detail
  - API: `/admin/api/research/ideas?sort=conviction_desc&limit=50`

- [ ] **Idea Detail Expansion** - Shows:
  - Full title + description
  - Source agent + analysis date
  - Key signals with percentages (signal1: +12%, signal2: -3%, etc.)
  - Confidence breakdown
  - Linked theses (if any): [T-12] "Long duration"
  - Recent updates (timeline)
  - Actions: [Create Thesis] [Archive] [View Lineage]
  - API: `/admin/api/research/ideas/{idea_id}`

- [ ] **Create Thesis from Idea** - Button triggers modal:
  - Pre-fill conviction from idea
  - Allow override conviction
  - Set initial allocation: $[_____] K
  - Select asset class(es): [Equities] [Options] [Crypto] [FX]
  - Linked to source idea_id
  - [Create] button executes: `POST /admin/api/theses` with idea_id
  - API: `POST /admin/api/theses`

- [ ] **Archive Idea** - Mark as solved/irrelevant
  - Confirmation modal: "Archive idea? It won't generate new theses."
  - API: `PUT /admin/api/research/ideas/{idea_id}` (status: ARCHIVED)

- [ ] **View Idea Lineage** - Shows:
  - Agent(s) that discovered it
  - Data sources + timestamps
  - Signal reasoning (SHAP values if available)
  - All theses created from this idea
  - API: `/admin/api/research/ideas/{idea_id}/lineage`

- [ ] **Idea Performance Tracking** - Stats if idea has linked theses:
  - Avg conviction: X%
  - Weighted PnL from linked theses: +$X
  - Hit rate if closed: X%
  - API: `/admin/api/research/ideas/{idea_id}/performance`

### Idea Auto-Discovery
- [ ] **Pause/Unpause Discovery** - Toggle discovery task on/off
  - Applies to single idea type or all discovery
  - API: `PUT /admin/api/discovery/config` (paused: true/false)

- [ ] **Discovery Task Queue Status** - Shows:
  - Ideas queued for discovery: N
  - Current discovery task: "Tech sector scan" (progress: 35%)
  - Estimated time to complete: 2.1 hours
  - API: `/admin/api/discovery/queue`

---

## Panel 3: THESES & POSITIONS (22 features)

### Thesis Tracking
- [ ] **Thesis List Table** - Columns:
  - ID | TITLE | CONVICTION % | ALLOCATION ($K) | PnL ($K) | EXIT SIGNAL
  - Sortable: by conviction, PnL, allocation, exit signal
  - Color-coded conviction: green (>60%), yellow (40-60%), red (<40%)
  - Color-coded PnL: green (profit), red (loss)
  - Color-coded exit signal: green (HOLD), yellow (WARN), red (EXIT)
  - API: `/admin/api/theses?sort=conviction_desc&limit=100`

- [ ] **Filter by Status** - Dropdown: ALL, ACTIVE, CLOSING, CLOSED
  - Default: ACTIVE
  - API: `/admin/api/theses?status=ACTIVE`

- [ ] **Thesis Detail Expansion** - Shows:
  - Conviction trajectory (chart): 30-day rolling conviction
  - Signal composition breakdown (pie/bar): which signals drive conviction?
  - Current allocation: $X | Max: $Y | Margin: $Z
  - Holdings linked to thesis (table): Position | Symbol | Size | PnL | Entry Date
  - Exit signal monitor: Floor conviction, current, buffer
  - Max loss allowed: $X | Current: $Y ✅/❌
  - Recent updates (timeline): "Conv +8% (CPI data)", "Position added: GOVT.US"
  - Actions: [Edit conviction] [Increase allocation] [Review exits] [Close thesis] [View lineage] [View audit]
  - API: `/admin/api/theses/{thesis_id}`

- [ ] **Edit Conviction Manually** - Modal:
  - Current conviction: X%
  - New conviction: [____] %
  - Reason: [Text input]
  - Warning: "This overrides AI signal by ±Y%"
  - [Save] button: `PUT /admin/api/theses/{thesis_id}/conviction`
  - Logs decision to audit trail
  - API: `PUT /admin/api/theses/{thesis_id}/conviction`

- [ ] **Increase Allocation** - Modal:
  - Current allocation: $X
  - Max allowed: $Y
  - Available to deploy: $Z (= Y - X)
  - New allocation: [____] K
  - [Approve] button: `PUT /admin/api/theses/{thesis_id}/allocation`
  - Requires CEO approval (routed to approvals panel)
  - API: `PUT /admin/api/theses/{thesis_id}/allocation`

- [ ] **Review & Approve Exits** - Shows:
  - Current conviction: X%
  - Floor threshold: Y% (trigger to close)
  - Status: HOLD / WARN / EXIT (based on distance to floor)
  - Proposed exit action (if triggered): "Close thesis, realize $+X PnL"
  - [Approve Exit] [Extend Thesis] buttons
  - API: `PUT /admin/api/theses/{thesis_id}/exit_action`

- [ ] **Close Thesis Manually** - Modal:
  - Reason: [Dropdown: "Manual stop-loss", "Change of mind", "Risk override", "Other"]
  - Notes: [Text]
  - Show current PnL: +$X
  - [Close Thesis] triggers: `PUT /admin/api/theses/{thesis_id}/status` (CLOSED)
  - All linked positions get closed (market order)
  - API: `PUT /admin/api/theses/{thesis_id}/status`

### Holdings & Positions
- [ ] **Holdings Table** - Positions linked to active thesis:
  - Symbol | Quantity | Current Price | Entry Price | Entry Date | Unrealized PnL | % of Thesis
  - Sortable: by symbol, quantity, PnL
  - Click row to view position detail
  - API: `/admin/api/theses/{thesis_id}/holdings`

- [ ] **View Position Detail** - Modal:
  - Security info: Symbol, Name, Asset Class, Sector
  - Entry: Date, Price, Quantity, Notional
  - Current: Price, Value, Unrealized PnL
  - Exit plan: Stop loss, Take profit, Time-based exit
  - Order history: List of fills for this position
  - [Edit exit plan] [Liquidate] [Transfer to other thesis]
  - API: `/admin/api/positions/{position_id}`

- [ ] **Thesis Performance Attribution** - Shows:
  - Entry date, Current date, Holding period
  - Absolute PnL: +$X
  - % return: +Y%
  - Annualized return: Z%
  - Max unrealized drawdown during holding
  - Contribution to fund PnL: X%
  - Chart: Position value over time
  - API: `/admin/api/theses/{thesis_id}/attribution`

- [ ] **Conviction History Chart** - Line chart:
  - X-axis: dates (30d rolling)
  - Y-axis: conviction % (0-100)
  - Line color: conviction level
  - Tooltip on hover: date, conviction %, driving signals
  - Annotations: key events ("CPI surprise", "Position added")
  - API: `/admin/api/theses/{thesis_id}/conviction_history`

---

## Panel 4: RISK & POLICY (19 features)

### Risk Metrics Dashboard
- [ ] **Value at Risk (VaR)** - Display:
  - 1-day, 95% confidence
  - Current: $X (Y%)
  - Historical avg (30d): $Z
  - Max allowed: $A
  - Margin to limit: $B (C%)
  - Rolling chart: 30d VaR history
  - API: `/admin/api/risk/var`

- [ ] **Expected Shortfall (CVaR)** - Display:
  - 1-day tail loss
  - Current: $X
  - Max allowed: $Y
  - Margin: Z%
  - Explanation: "Worst 5% of days costs $X on average"
  - API: `/admin/api/risk/cvar`

- [ ] **Maximum Drawdown** - Display:
  - Current: -X%
  - High water mark: $Y (date)
  - Current NAV: $Z
  - Max allowed: -A%
  - Margin: -B% (safe buffer)
  - API: `/admin/api/risk/drawdown`

- [ ] **Gross Leverage** - Display:
  - Current: 1.2x
  - Max allowed: 1.5x
  - Long gross: 1.15x
  - Short gross: 0.05x
  - API: `/admin/api/risk/leverage`

- [ ] **Sharpe Ratio** - Display:
  - Rolling 30d: X
  - Target: > 1.0
  - 30d return: +A%
  - 30d volatility: B%
  - API: `/admin/api/risk/sharpe`

### Policy Enforcement
- [ ] **Sector Concentration Limits** - Display table:
  - Sector | Allocation % | Max % | Margin %
  - Top 3 sectors highlighted
  - Color-coded: green if margin > 5%, yellow if 2-5%, red if < 2%
  - Editable: Change max % per sector
  - API: `/admin/api/policy/sector_limits`

- [ ] **Correlation Risk Monitor** - Display:
  - Highest correlated pair: Symbol1 + Symbol2 (correlation)
  - Expected range: X–Y
  - Status: OK / WARN / BREACH
  - Show all pairs in table (sortable)
  - API: `/admin/api/risk/correlation`

- [ ] **Position Size Limits** - Display:
  - Max single position: 8% of AUM
  - Current max position: 6.2%
  - Min position to trade: $10K
  - Current min position: $42K
  - Editable thresholds
  - API: `/admin/api/policy/position_limits`

- [ ] **Market Hours & Session Rules** - Display:
  - Current time (UTC)
  - US session: 🟢 OPEN (closes 21:00 UTC)
  - Crypto: 🟢 24/5
  - FX: 🟢 OPEN
  - Options: 🟢 OPEN
  - Color-coded: green = open, gray = closed, yellow = closing soon
  - API: `/admin/api/market/hours`

- [ ] **Trade Approval Thresholds** - Display (editable):
  - Any trade > $X notional: requires approval
  - Any trade against active thesis: auto-approved
  - Any trade in illiquid asset: requires approval
  - [Edit thresholds] button
  - API: `/admin/api/policy/approval_thresholds`

### Risk Alerts
- [ ] **Risk Alert List** - Shows:
  - Alert type: Risk limit breached, Policy violation, Data issue, etc.
  - Severity: 🔴 Critical, 🟡 Warning
  - Description: "Sector concentration 32% > limit 30%"
  - Action taken: "Trade automatically rejected"
  - Timestamp
  - [Acknowledge] [View details] [Override]
  - API: `/admin/api/alerts/risk`

- [ ] **Risk Limit History** - Log of all breaches:
  - Date, metric, limit, actual, action (blocked/override), by whom
  - Searchable, filterable
  - Export to CSV
  - API: `/admin/api/risk/breach_history`

---

## Panel 5: EXECUTION & ORDERS (20 features)

### Orders Management
- [ ] **Orders List Table** - Columns:
  - ORDER_ID | STATUS | SYMBOL | SIDE | SIZE | PRICE | TIME | SLIPPAGE
  - Filterable: Status (ALL, PENDING, FILLED, PARTIAL, CANCELLED)
  - Filterable: Time (TODAY, THIS WEEK, THIS MONTH, ALL)
  - Filterable: Type (ALL, BUY, SELL, SHORT)
  - Sortable: by date desc (most recent first), status, slippage
  - API: `/admin/api/orders?status=FILLED&time=TODAY`

- [ ] **Order Detail Expansion** - Shows:
  - Execution context: Thesis link, Signal conviction, Approval status
  - Order details: Instrument, Quantity, Type (MARKET/LIMIT), Time in force
  - Execution: Submitted time, Filled time, Fill quantity, Fill price avg
  - Broker: Paper broker, Commission, Execution quality
  - Slippage analysis: VWAP at order time, Slippage %, "Outperformed VWAP"
  - Cost breakdown: Price + Commission + Slippage = Total cost
  - Actions: [View fills] [View tape] [Audit trail] [Revert?]
  - API: `/admin/api/orders/{order_id}`

- [ ] **View Order Fills** - Modal/table:
  - Detailed fill breakdown (for large orders that filled in multiple fills)
  - Timestamp | Qty | Price | Venue | Commission
  - Total qty filled, avg price, total commission
  - API: `/admin/api/orders/{order_id}/fills`

- [ ] **Execution Quality Analysis** - Shows:
  - VWAP at order time
  - Actual avg fill price
  - Slippage (bps): Actual - VWAP
  - Interpretation: "Favorable" / "In line" / "Unfavorable"
  - Root cause (if analysis available): "Low spread", "High volume", etc.
  - API: `/admin/api/orders/{order_id}/execution_quality`

- [ ] **Order Cancellation** - For pending orders:
  - [Cancel] button, confirmation modal
  - Logs cancellation reason + timestamp
  - API: `PUT /admin/api/orders/{order_id}` (status: CANCELLED)

### Manual Order Submission
- [ ] **Manual Order Form** - Fields:
  - Symbol: [Autocomplete dropdown]
  - Type: [MARKET / LIMIT dropdown]
  - Side: [BUY / SELL / SHORT dropdown]
  - Quantity: [____] units
  - Limit Price: [____] (if LIMIT type)
  - Time in force: [IOC / GTC / DAY dropdown]
  - Reason/Notes: [Text input]
  - Linked thesis: [Dropdown or NONE]
  - [Real-time risk check]: Shows notional, margin check, etc.
  - [Override & Submit] [Cancel] buttons
  - API: `POST /admin/api/orders`

- [ ] **Order Validation** - Before submit:
  - Check notional vs limits
  - Check sector concentration impact
  - Check correlation risks
  - Show warnings if applicable
  - Allow override if CEO approves
  - API: `POST /admin/api/orders/validate`

- [ ] **Fill Notifications** - Real-time updates:
  - When order fills: notification toast "Order O-89 filled: 2800 units"
  - Fill details: quantity, price, time, slippage
  - Option to expand to detail view
  - API: WebSocket stream `/admin/api/orders/stream`

- [ ] **Order Tape** - Historical log of all fills:
  - Timestamp | Symbol | Side | Qty | Price | Venue | Slippage
  - Filterable by date range, symbol, side
  - Export to CSV
  - API: `/admin/api/orders/tape`

### Execution Settings
- [ ] **Broker Configuration** - Display (edit):
  - Current broker: Paper broker (simulated)
  - Status: Ready
  - Commission: 0 bps
  - Slippage model: Simple (fixed % of spread)
  - Settlement: T+2 (default, not configurable)
  - When live: Multiple brokers with failover
  - API: `/admin/api/broker/config`

- [ ] **Execution Priority** - Rules (editable):
  - Order execution priority: [SPEED / QUALITY / COST dropdown]
  - SPEED = immediate execution, accept higher slippage
  - QUALITY = best execution, may take longer
  - COST = minimize slippage, use smart order routing
  - API: `/admin/api/execution/priority`

---

## Panel 6: AGENTS & RUNTIME (21 features)

### Agent Roster
- [ ] **Agent List Table** - Columns:
  - AGENT_ID | ROLE | STATUS | TASKS (active/queued) | CPU | MEM
  - Status indicators: 🟢 READY, 🟡 BUSY, ⏸️ PAUSED, 🔴 ERROR
  - Sortable: by status, tasks, CPU usage
  - Click row to view agent detail
  - API: `/admin/api/agents/roster`

- [ ] **Agent Detail View** - Shows:
  - Agent name, role, status
  - Uptime, last heartbeat
  - Tasks (active + queued)
  - Resource usage: CPU %, Memory MB
  - LLM provider assigned: Claude / GPT-4 / Gemini
  - Performance metrics: Avg task time, success rate, error rate
  - Recent errors (if any): list with timestamps
  - Actions: [Pause] [Resume] [Restart] [View logs]
  - API: `/admin/api/agents/{agent_id}`

- [ ] **Active Tasks List** - Shows all running tasks:
  - Task ID | Agent | Description | Status | Progress | Time elapsed | Est. remaining
  - Expandable: shows task details, intermediate outputs
  - Sortable: by progress, time elapsed
  - Actions: [View details] [View logs] [Pause] [Stop] [Let it finish]
  - API: `/admin/api/agents/tasks/active`

- [ ] **Task Detail Panel** - Shows:
  - Task ID, Agent, Status, Progress bar (%)
  - Task description: "Fed pivot signal strength"
  - Data sources: 5/5 ready
  - Output progress: Intermediate results if available
  - Logs: Last 50 log lines (tail -50)
  - Estimated completion time
  - [Pause] [Stop] [Retry] buttons
  - API: `/admin/api/agents/tasks/{task_id}`

- [ ] **Agent Performance Metrics** - Table:
  - Agent | Avg task time | Success rate | Error rate | Total tasks completed
  - Color-coded: green if success > 95%, yellow if 80-95%, red if < 80%
  - [View detailed history] link
  - API: `/admin/api/agents/performance`

- [ ] **Agent Logs** - View full logs for an agent:
  - Real-time tail (new logs appear at bottom)
  - Search/filter by keyword
  - Log level filter: DEBUG / INFO / WARN / ERROR
  - Download logs as .txt file
  - API: `/admin/api/agents/{agent_id}/logs`

### LLM Routing & Management
- [ ] **LLM Vendor Status** - Shows 3 vendors:
  - Claude (Anthropic): 🟢 HEALTHY | Uptime 99.8% | Queue: 3/10 | Token budget: $127/$450 (28%)
  - GPT-4 (OpenAI): 🟡 DEGRADED | Uptime 95.2% | Queue: 2/10 | Token budget: $98/$300 (33%)
  - Gemini (Google): 🟢 READY | Uptime 99.5% | Queue: 0/10 | Token budget: $0/$100 (0%)
  - Primary: Claude | Fallbacks: GPT-4, Gemini
  - API: `/admin/api/llm/vendors`

- [ ] **LLM Routing Configuration** - (Editable):
  - Primary vendor: [Claude ▼]
  - Fallback 1: [GPT-4 ▼]
  - Fallback 2: [Gemini ▼]
  - Auto-failover: [ON ▼]
  - [Manage vendors] [View costs] [Adjust routing]
  - API: `/admin/api/llm/routing/config`

- [ ] **LLM Cost Management** - Display:
  - Monthly budgets per vendor
  - Current spend per vendor
  - Cost projections (if current pace continues)
  - Auto-stop when budget reached: [ON/OFF]
  - Alert at 80% of budget: [ON/OFF]
  - API: `/admin/api/llm/costs`

- [ ] **LLM Failover History** - Log:
  - Date | Request | Primary vendor | Reason for failover | Fallback used | Result
  - Shows if primary vendor was down/slow, how fallback performed
  - API: `/admin/api/llm/failover_history`

### Orchestrator Control
- [ ] **Runtime State** - Display:
  - 🟢 RUNNING / 🟡 DEGRADED / 🔴 STOPPED
  - Uptime: X days Y hours Z minutes
  - Last heartbeat: 0.3s ago
  - Memory usage: 256 MB / 1 GB
  - CPU usage: 12%
  - API: `/admin/api/orchestrator/status`

- [ ] **Pause Orchestration** - Button:
  - Confirmation modal: "Pause? Agents will stop, no new tasks will start."
  - Result: orchestrator.paused = true
  - Existing running tasks continue (no interrupt)
  - API: `PUT /admin/api/orchestrator/control` (action: pause)

- [ ] **Resume Orchestration** - Button:
  - Unpause, restart task queue
  - API: `PUT /admin/api/orchestrator/control` (action: resume)

- [ ] **Restart Orchestration** - Button:
  - Confirmation: "Restart? Running tasks will be interrupted."
  - Clears task queue, resets agent state
  - API: `PUT /admin/api/orchestrator/control` (action: restart)

- [ ] **Reset Orchestration** - Button:
  - Confirmation: "Full reset? Knowledge graph will be rebuilt."
  - Dangerous operation, rebuild from scratch
  - API: `PUT /admin/api/orchestrator/control` (action: reset)

---

## Panel 7: APPROVALS & CEO DIGESTS (18 features)

### Pending Approvals
- [ ] **Approvals Queue** - List of decisions pending CEO approval:
  - Type (Capital allocation, New hypothesis, Manual trade, Risk override)
  - Description
  - Who/what requested it
  - When it was submitted
  - Context data needed for decision
  - Actions: [APPROVE] [REJECT] [ASK_AGENT] [MODIFY]
  - API: `/admin/api/approvals/pending`

- [ ] **Capital Allocation Approval Modal** - Shows:
  - Thesis: Link + conviction + current allocation + max
  - Recommendation: "Deploy $200K to T-12"
  - Risk check: OK / WARN
  - Agent reasoning: Why this allocation?
  - Your decision options: [APPROVE] [APPROVE w/ notes] [REJECT] [ASK_AGENT]
  - Notes field: [Text input]
  - API: `POST /admin/api/approvals/{approval_id}/decide`

- [ ] **New Thesis Approval Modal** - Shows:
  - Research idea: Link to R-XX
  - Conviction: Y%
  - Proposed allocation: $Z
  - Suggested positions: [Symbol1, Symbol2, ...]
  - Risk impact: Sector concentration +X%, Correlation OK
  - Your options: [APPROVE THESIS] [MODIFY & APPROVE] [REJECT]
  - API: `POST /admin/api/approvals/{approval_id}/decide`

- [ ] **Manual Trade Approval Modal** - Shows:
  - Trade: BUY/SELL Symbol at Price for Quantity
  - Notional: $X (vs your threshold of $Y)
  - Reason: "CEO discretionary entry"
  - Risk review: OK / WARN
  - Linked thesis: T-XX or None
  - Your options: [APPROVE] [APPROVE w/ notes] [REJECT]
  - API: `POST /admin/api/approvals/{approval_id}/decide`

- [ ] **Risk Override Approval Modal** - Shows:
  - Override type: "Increase sector concentration beyond limit"
  - Current: 32% | Limit: 30% | Proposed: 35%
  - Justification: "Strong conviction on sector thesis"
  - Agent warning: "This breaches sector policy"
  - Your options: [ALLOW OVERRIDE] [DENY] [REQUIRE_MORE_INFO]
  - API: `POST /admin/api/approvals/{approval_id}/decide`

- [ ] **Bulk Approval** - (Optional advanced feature)
  - Checkbox to select multiple pending approvals
  - [Approve Selected] button (for routine items)
  - Shows summary: "Approve 5 items: X theses, Y allocations?"
  - API: `POST /admin/api/approvals/bulk_decide`

### Approval History
- [ ] **Approval History Table** - Shows past 30d decisions:
  - DATE | DECISION | RESULT (APPROVED/REJECTED) | OUTCOME (PnL if closed)
  - Sortable: by date, result, outcome
  - Filterable: by result, decision type
  - Click row to see details
  - API: `/admin/api/approvals/history?days=30`

- [ ] **Approval Detail View** - Shows:
  - Full decision data + your notes when you approved/rejected
  - Result: What happened after you decided?
  - If thesis: Current PnL, conviction, status
  - If trade: Filled price, slippage, unrealized PnL
  - Lessons: Was decision good in hindsight?
  - API: `/admin/api/approvals/{approval_id}/detail`

### Daily CEO Digest
- [ ] **Generate Daily Digest** - Auto-generated at 18:00 UTC:
  - Today in numbers: PnL, exposure, Sharpe, trades executed
  - Active theses snapshot: ID, allocation, conviction, PnL
  - Key decisions made (with results)
  - Market context: VIX, Fed expectations, sector rotation
  - Agents working on: List of active tasks
  - Risk status: All green or alerts?
  - Things to review: Highlighted action items
  - API: `/admin/api/digests/daily`

- [ ] **Email Digest** - Option to email digest to stakeholders:
  - [Email to [email_1, email_2, ...]]
  - Template: HTML version of digest
  - Add custom message field
  - Scheduled sends: [Immediately] [Tomorrow morning]
  - API: `POST /admin/api/digests/send_email`

- [ ] **Digest Customization** - (Advanced):
  - Which metrics to include: NAV, Sharpe, drawdown, sector breakdown
  - Which narratives: Market context, agent summary, risk status
  - Recipient list: CEO, investors, team
  - Frequency: Daily, Weekly, Monthly
  - [Save digest template]
  - API: `/admin/api/digests/config`

- [ ] **Digest History** - View past digests:
  - List of digests by date
  - Click to view full digest
  - Export as PDF
  - Email again to stakeholders
  - API: `/admin/api/digests/history`

---

## Panel 8: AUDIT & LINEAGE (16 features)

### Decision Search & Log
- [ ] **Decision Search** - Filters:
  - Type: [ALL] [THESIS_CREATION] [TRADE] [APPROVAL] [SIGNAL_UPDATE]
  - Date range: [TODAY] [THIS WEEK] [THIS MONTH] [CUSTOM]
  - Status: [ALL] [APPROVED] [REJECTED] [EXECUTED] [PENDING]
  - Search by ID: [decision_id___]
  - API: `/admin/api/decisions/search?type=TRADE&status=EXECUTED`

- [ ] **Decision Log Table** - Shows:
  - DATE | DECISION | TYPE | STATUS | [Details]
  - Sortable: by date (desc, most recent), status, type
  - Click row to expand or [Details] to open full panel
  - API: `/admin/api/decisions/log?limit=100`

- [ ] **Decision Detail Lineage** - Shows full chain:
  - [LEVEL 1] Data trigger (e.g., "CPI data released")
  - [LEVEL 2] Signal update (e.g., "Fed pivot conviction +8%")
  - [LEVEL 3] Thesis decision (e.g., "Create thesis T-12")
  - [LEVEL 4] Approval decision (e.g., "CEO approves $400K")
  - [LEVEL 5] Execution decision (e.g., "Create trade O-89")
  - [LEVEL 6] Outcome (e.g., "Order filled at $101.23")
  - Each level shows: Agent, model version, inputs, outputs, confidence
  - Expandable: See SHAP values, model reasoning, etc.
  - API: `/admin/api/decisions/{decision_id}/lineage`

- [ ] **SHAP Value Display** - For ML decisions:
  - Feature importance: which factors drove the decision?
  - Bar chart: feature name vs SHAP impact
  - Hover: see actual values
  - For transparency + understanding model logic
  - API: `/admin/api/decisions/{decision_id}/explainability`

- [ ] **Risk Gate Decision Log** - Shows:
  - All risk gate checks that happened for a trade
  - Check type: Leverage, VaR, sector concentration, etc.
  - Result: PASSED / BREACHED / OVERRIDE
  - If override: who approved, why, when
  - API: `/admin/api/decisions/{trade_id}/risk_gates`

### Lineage Export
- [ ] **Export Lineage** - Button:
  - Format: JSON, CSV, or PDF report
  - Includes full decision chain
  - Includes all intermediate values
  - For compliance, audits, post-mortem
  - API: `/admin/api/decisions/{decision_id}/export`

- [ ] **Compliance Report** - (Automated or on-demand):
  - All decisions made in date range
  - Risk gates applied
  - Overrides and approvals
  - PnL realized per decision
  - Export as formal audit report
  - API: `/admin/api/compliance/report`

---

## Panel 9: MARKET CONTEXT (14 features)

### Regime Classification
- [ ] **Current Regime Display** - Shows:
  - Regime name: RISK_ON_GROWTH / RISK_OFF_FLIGHT / STAGFLATION / VOLATILE_CHOP
  - Confidence: 78%
  - Duration in regime: 8 days
  - Regime probabilities: Pie/bar chart
  - Last regime switch: Date + reason
  - API: `/admin/api/market/regime`

- [ ] **Regime History Chart** - Visual:
  - Timeline: X = dates, Y = regime (colored bands)
  - Show last 12 months
  - Duration of each regime
  - Trigger for switch (if annotated)
  - API: `/admin/api/market/regime_history`

### Macro Factor Display
- [ ] **Growth Indicators** - Display:
  - US GDP nowcast: 2.3%
  - ISM PMI: 52.1 (Expansion status)
  - Job creation (30d avg): 189K
  - Earnings revisions: +0.8% YoY
  - Trends: up/down/flat arrows
  - API: `/admin/api/market/growth_indicators`

- [ ] **Inflation Indicators** - Display:
  - CPI (headline): 3.2% YoY
  - Core CPI: 3.8% YoY
  - Fed expectations: 2.5% by Dec
  - Market inflation breakevens: 2.3%
  - Trends with arrows
  - API: `/admin/api/market/inflation_indicators`

- [ ] **Monetary Policy Status** - Display:
  - Fed Funds Rate: 5.25%–5.50%
  - Probability of cut by Q3: 75%
  - Market-implied cuts: 2
  - QT status: $60B/month runoff
  - API: `/admin/api/market/monetary_policy`

- [ ] **Sentiment & Risk Indicators** - Display:
  - VIX: 18.2 (real-time)
  - Put/call ratio: 0.78
  - Credit spreads (IG OAS): 98 bps
  - Term premium (10Y–2Y): 1.8%
  - API: `/admin/api/market/sentiment`

- [ ] **Commodity & Currency Display** - Display:
  - USD Index: 103.4 (trend)
  - Oil (WTI): $82/bbl
  - Gold: $2,042/oz
  - Bitcoin: $42,300
  - Trends with % changes
  - API: `/admin/api/market/commodities`

### Regime Implications
- [ ] **Model Routing for Current Regime** - Shows:
  - Which signals to favor in this regime
  - Which models to weight more heavily
  - Which positions to favor/avoid
  - Warning: If any thesis is regime-mismatched
  - Example: "T-12 (duration) underperforms in RISK_ON, consider rebalancing"
  - API: `/admin/api/market/regime_implications`

- [ ] **Economic Calendar** - Shows:
  - Next 7 days of economic releases
  - Event name, time, importance (🔴 HIGH / 🟡 MEDIUM / 🟢 LOW)
  - Surprise vs consensus tracking (after release)
  - Market reaction tracking
  - API: `/admin/api/market/economic_calendar`

---

## Panel 10: SETTINGS & CONFIGURATION (17 features)

### Risk Configuration
- [ ] **Risk Limits Editor** - Editable fields:
  - Max VaR (daily, 95%): $[____]K
  - Max Drawdown: -[____]%
  - Max Leverage (gross): [____]x
  - Max position size: [____]%
  - Max sector concentration: [____]%
  - Min correlation score: [____]
  - [Save] [Reset to defaults] [Import from file]
  - API: `PUT /admin/api/settings/risk_limits`

### Approval Thresholds
- [ ] **Approval Size Thresholds** - Editable:
  - Manual trades > $[____]K require approval
  - Daily cumulative > $[____]K
  - New thesis allocation > $[____]K
  - Conviction override ±[____]%
  - API: `PUT /admin/api/settings/approval_thresholds`

- [ ] **Auto-Approve Rules** - Checkboxes:
  - ☑️ Trades linked to active thesis
  - ☑️ Rebalance trades within thesis
  - ☑️ Stop-loss orders (auto-triggered)
  - ☐ Discretionary new theses < $50K
  - API: `PUT /admin/api/settings/auto_approve_rules`

### Agent Configuration
- [ ] **Discovery Frequency** - Dropdown:
  - [Every 1h ▼]
  - Updates agent task scheduling
  - API: `PUT /admin/api/settings/agent_config`

- [ ] **Max Concurrent Tasks** - Field:
  - Max discovery tasks running simultaneously: [3 ▼]
  - API: `PUT /admin/api/settings/agent_config`

- [ ] **Autopilot Toggle & Settings** - Radio buttons:
  - ☑️ Agent autopilot: [ON ▼]
  - Autopilot creation threshold: [60% ▼]
  - Autopilot allocation limit: [$100K ▼] per thesis
  - API: `PUT /admin/api/settings/autopilot`

### LLM Budget Management
- [ ] **LLM Budget Configuration** - Editable:
  - Claude monthly budget: $[____]
  - GPT-4 monthly budget: $[____]
  - Gemini monthly budget: $[____]
  - Auto-stop when reached: [ON ▼]
  - Alert at 80%: [ON ▼]
  - API: `PUT /admin/api/settings/llm_budgets`

### UI & Notifications
- [ ] **Theme & Font Settings** - Dropdowns:
  - Theme: [Dark ▼] (light theme when implemented)
  - Font size: [Medium ▼]
  - API: `PUT /admin/api/settings/ui`

- [ ] **Alert Notification Preferences** - Checkboxes:
  - ☑️ Critical (risk limit breached)
  - ☑️ Approvals pending
  - ☑️ Large trades (> $100K filled)
  - ☑️ Macro events (high importance)
  - ☐ Routine agent tasks
  - API: `PUT /admin/api/settings/notifications`

- [ ] **Digest Schedule & Channels** - Fields:
  - Digest frequency: [Daily @ 18:00 UTC ▼]
  - Channels: ☑️ In-app ☑️ Email ☑️ Slack
  - Email recipients: [___@___.com, ___@___.com]
  - [Test notification]
  - API: `PUT /admin/api/settings/digest_schedule`

### Operational Settings
- [ ] **Trading Hours Configuration** - Dropdowns:
  - Trading hours: [US market 09:30–16:00 EST ▼]
  - Pre-market trading: [OFF ▼]
  - After-hours trading: [OFF ▼]
  - Weekend/holiday trading: [OFF ▼]
  - API: `PUT /admin/api/settings/trading_hours`

- [ ] **Paper vs Live Mode Toggle** - Radio:
  - ☑️ Paper mode: [ON] (locked, no live until migration ready)
  - ☐ Live mode: [Not available]
  - When switching to live: Manual migration + compliance review
  - API: Read-only for now, `PUT /admin/api/settings/mode` when live ready

- [ ] **Data Refresh Rate** - Dropdowns:
  - UI refresh: [Real-time ▼]
  - Historical data update: [02:00 UTC ▼]
  - API: `PUT /admin/api/settings/data_refresh`

- [ ] **Settings Export/Import** - Buttons:
  - [Export all settings] → JSON file (backup)
  - [Import settings] → Load from file
  - [Reset to defaults] → Confirm + reset all
  - API: `GET /admin/api/settings/export`, `POST /admin/api/settings/import`

---

## Panel 11: KNOWLEDGE GRAPH & MEMORY (16 features)

### Fund Statistics
- [ ] **Knowledge Stats Display** - Shows:
  - Total decisions logged: X
  - Total theses created: Y
  - Active theses: Z
  - Total trades executed: A
  - Research ideas discovered: B
  - Learning loops completed: C
  - Knowledge graph size: D GB
  - Last backup: timestamp
  - API: `/admin/api/knowledge/stats`

### Memory Queries
- [ ] **Query Interface** - Text input:
  - "What theses have worked best?"
  - "When did we last see this signal pattern?"
  - "What macros lead to sector rotation?"
  - System answers with data + charts
  - API: `POST /admin/api/knowledge/query` (uses RAG or similar)

- [ ] **Signal Performance Memory** - Shows:
  - Best-performing signals: List with win rates
  - Worst-performing signals: List with win rates
  - Recommendation: "Deweight technical, boost fundamental"
  - API: `/admin/api/knowledge/signal_performance`

- [ ] **Decision Bias Analysis** - Shows:
  - Approval rate: 97% (you approve most agent recommendations)
  - Avg approval size: $310K
  - Avg rejection size: $127K (you reject smaller bets)
  - Win rate by type: Macro 64%, Fundamental 71%, Technical 52%
  - Interpretation: "You're better at fundamental + macro than technical"
  - API: `/admin/api/knowledge/decision_bias`

- [ ] **Fund Narrative** - Auto-generated narrative:
  - Your fund story (30–100 words)
  - Key strengths identified
  - Areas for improvement
  - Forward-looking recommendations
  - Updated weekly
  - [Generate new narrative] [Share narrative]
  - API: `/admin/api/knowledge/narrative`

### Knowledge Management
- [ ] **Knowledge Graph Explorer** - (Advanced):
  - Visual graph: nodes = decisions, edges = relationships
  - Click node to see details
  - Search within graph
  - Filter by type, date, status
  - View subgraphs (e.g., all decisions from R-47)
  - API: `/admin/api/knowledge/graph`

- [ ] **Rebuild Knowledge Store** - Admin action:
  - [Rebuild] button with confirmation
  - Reconstructs graph from decision ledger
  - Useful if data corruption or need to reindex
  - Shows progress: "Rebuilding... 45% complete"
  - API: `POST /admin/api/knowledge/rebuild`

- [ ] **Memory Reset** - Admin action:
  - [Reset] button with strong confirmation
  - Clears all fund memory, resets to start
  - Dangerous, rarely used
  - API: `POST /admin/api/knowledge/reset`

- [ ] **Memory Export** - Button:
  - Export fund memory as JSON
  - Include: all decisions, theses, signals, learnings
  - For archival or sharing with team
  - API: `/admin/api/knowledge/export`

---

## Summary Stats

- **Total Features**: 127
- **Core Panels**: 11
- **Core API Endpoints**: 80+
- **Real-time Streams**: 5 (NAV, orders, agent tasks, risk alerts, digest digest)
- **Estimated Frontend Components**: 40–50 (buttons, modals, tables, charts)
- **Authentication**: JWT with refresh tokens
- **Rate Limiting**: Per-user, per-endpoint
- **Accessibility**: WCAG AAA

---

## Implementation Priority

**Phase 1 (MVP, 4 weeks)**:
1. Overview
2. Research & Discovery
3. Theses & Positions
4. Risk & Policy
5. Execution & Orders

**Phase 2 (4 weeks)**:
6. Agents & Runtime
7. Approvals & CEO Digests
8. Audit & Lineage

**Phase 3 (2 weeks)**:
9. Market Context
10. Settings & Configuration

**Phase 4 (2 weeks)**:
11. Knowledge Graph & Memory
+ Polish, testing, hardening

**Total: 12 weeks to full feature parity**

---

**Document Version**: 1.0  
**Status**: Ready for engineering sprint planning  
**Last Updated**: 2026-05-23

