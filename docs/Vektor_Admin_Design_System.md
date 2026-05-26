# Vektor Admin Control Center
## Design System & Visual Specification

**Version**: 1.0  
**Date**: 2026-05-23  
**Purpose**: Complete design guide for implementation team

---

## Part 1: Design System Foundation

### 1.1 Color Palette

**Primary Palette** (Dark theme - institutional fund aesthetic):

```
Background:
  Deep: #0A0E27 (darkest backgrounds, modals)
  Base: #0F1535 (main background)
  Elevated: #151D47 (cards, panels)
  
Text:
  Primary: #E8EBF5 (main text, high contrast)
  Secondary: #A8B0D0 (secondary text, supporting)
  Tertiary: #7A84A8 (muted text, disabled)
  Inverse: #0A0E27 (text on light backgrounds)

Accent (Call-to-action):
  Primary: #00D4FF (bright cyan, actions)
  Hover: #00B8E6 (darker cyan, hover state)
  Active: #0099CC (even darker, pressed state)
  
Status Colors:
  Success: #00E676 (green, positive events)
  Warning: #FFC400 (amber, caution)
  Error: #FF4444 (red, critical)
  Info: #2196F3 (blue, informational)
  Neutral: #7A84A8 (gray, neutral)
  
Risk Colors (special meaning):
  Critical Risk: #FF4444 (red background + icon)
  High Risk: #FF8A00 (orange)
  Medium Risk: #FFC400 (yellow)
  Low Risk: #FFD700 (light yellow)
  Safe: #00E676 (green)
```

**Why this palette?**
- Dark theme reduces eye strain (fund managers work 8+ hour days)
- High contrast (WCAG AAA compliance for accessibility)
- Cyan + green + red = institutional clarity (not fintech-flashy)
- Risk colors are intuitive (red = danger, green = safe)

---

### 1.2 Typography

```
Font Stack (global):
font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif
(no custom fonts = faster load, universal availability)

Size Scale:
  xs: 11px  (smallest labels, timestamps)
  sm: 12px  (table headers, helper text)
  base: 13px (body text, standard)
  md: 14px  (UI labels)
  lg: 16px  (section titles)
  xl: 18px  (card titles)
  2xl: 22px (panel titles)
  3xl: 28px (page titles)
  4xl: 32px (hero/dashboard KPIs)

Weight Scale:
  regular: 400 (body, labels)
  medium: 500 (headers, strong text)
  semibold: 600 (titles, highlights)
  bold: 700 (emphasis, alerts)

Line Height:
  Tight: 1.2 (labels, numbers)
  Normal: 1.5 (body text)
  Relaxed: 1.8 (long-form text)

Letter Spacing:
  Tight: -0.01em (headings)
  Normal: 0 (standard)
  Wide: 0.02em (labels, all-caps)
```

**Examples**:

```
Page Title:
  size: 28px | weight: 600 | color: #E8EBF5 | margin-bottom: 24px

Section Title:
  size: 18px | weight: 600 | color: #E8EBF5 | margin-bottom: 16px

Body Text:
  size: 13px | weight: 400 | color: #A8B0D0 | line-height: 1.5

Label:
  size: 12px | weight: 500 | color: #7A84A8 | text-transform: uppercase

KPI Value:
  size: 32px | weight: 600 | color: #00D4FF | font-variant-numeric: tabular-nums

Table Cell:
  size: 13px | weight: 400 | color: #A8B0D0 | text-align: right (for numbers)
```

---

### 1.3 Spacing & Layout Grid

```
Base Unit: 4px

Spacing Scale:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 20px
  2xl: 24px
  3xl: 32px
  4xl: 40px
  5xl: 48px
  6xl: 56px
  7xl: 64px

Grid System: 12-column grid
  Column width: 64px + 16px gap = 80px per column
  Gutter: 16px (left/right margins)
  
Layout Rules:
  Page padding: 24px (desktop), 16px (tablet), 12px (mobile)
  Panel padding: 20px (standard)
  Card padding: 16px (small cards), 20px (large cards)
  Gap between items: 16px (standard), 12px (compact), 24px (loose)

Breakpoints:
  Mobile: < 640px (single column)
  Tablet: 640px–1024px (2 columns)
  Desktop: 1024px–1440px (3 columns)
  Large Desktop: > 1440px (4+ columns)
```

**Why 4px grid?**
- Flexible (can create 4px, 8px, 12px, 16px, 20px, etc.)
- Reduces design decisions
- Ensures vertical rhythm

---

### 1.4 Component Styles

#### Button Styles

```
PRIMARY ACTION (blue/cyan):
  Background: #00D4FF
  Text: #0A0E27 (inverse)
  Padding: 12px 20px
  Border-radius: 6px
  Border: none
  Font-size: 13px | Weight: 600
  Cursor: pointer
  Transition: all 150ms ease
  
  States:
    Hover: background #00B8E6, shadow 0 4px 12px rgba(0, 212, 255, 0.2)
    Active: background #0099CC, shadow inset 0 2px 4px rgba(0, 0, 0, 0.2)
    Disabled: background #3A4556, cursor not-allowed, opacity 0.5
    Loading: show spinner, disable interaction

SECONDARY ACTION (outlined):
  Background: transparent
  Border: 1px solid #3A4556
  Text: #00D4FF
  Padding: 12px 20px
  Border-radius: 6px
  
  States:
    Hover: background #151D47, border #00D4FF
    Active: border #0099CC, background #0A2540

DANGER ACTION (red):
  Background: #FF4444
  Text: #0A0E27
  Padding: 12px 20px
  Border-radius: 6px
  
  States:
    Hover: background #E63030
    Active: background #CC2828
    
SMALL/COMPACT BUTTON:
  Padding: 8px 12px
  Font-size: 12px
  Border-radius: 4px
```

**Common button states in Vektor**:
- `[Submit]` - primary action, blue
- `[Cancel]` [Reject]` - secondary, outlined
- `[Override]` [Force Execute]` - danger, red
- `[Export]` [Share]` - secondary, outlined
- `[Approve]` - success, green

#### Input Fields

```
Text Input:
  Background: #0A0E27
  Border: 1px solid #2A3558
  Border-radius: 4px
  Padding: 10px 12px
  Font-size: 13px
  Color: #E8EBF5
  
  States:
    Focus: border #00D4FF, box-shadow 0 0 0 2px rgba(0, 212, 255, 0.1)
    Error: border #FF4444, background #3A1616
    Disabled: background #151D47, opacity 0.5, cursor not-allowed
    
  Placeholder text: color #5A6478, font-style italic

Textarea:
  Same as text input, but min-height 120px, resize vertical only

Select/Dropdown:
  Same styling as text input
  Arrow icon: right-aligned, #7A84A8, pointer-events none
  
Radio/Checkbox:
  Size: 18px × 18px
  Background (unchecked): #151D47
  Border: 2px solid #3A4556
  Border-radius: 3px (checkbox), 50% (radio)
  
  Checked state:
    Background: #00D4FF
    Check mark: white, SVG icon
    
Toggle Switch:
  Width: 44px, Height: 24px
  Background (off): #2A3558
  Background (on): #00E676
  Circle: 20px, white, center
  Border-radius: 12px
  Transition: all 200ms ease
```

#### Card/Panel

```
Panel (standard container):
  Background: #151D47
  Border: 1px solid #2A3558
  Border-radius: 8px
  Padding: 20px
  Box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3)
  Margin-bottom: 16px
  
  Hover state (if clickable):
    Border-color: #3A4556
    Box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4)
    Transition: all 200ms ease

Alert Box (contextual):
  Border-left: 4px solid (color depends on type)
  Background: (tinted color, 10% opacity)
  Padding: 12px 16px
  Border-radius: 4px
  
  Error: border #FF4444, background rgba(255, 68, 68, 0.1)
  Warning: border #FFC400, background rgba(255, 196, 0, 0.1)
  Success: border #00E676, background rgba(0, 230, 118, 0.1)
  Info: border #2196F3, background rgba(33, 150, 243, 0.1)
```

#### Tables

```
Table Header Row:
  Background: #0A0E27
  Border-bottom: 2px solid #2A3558
  Text: size 12px, weight 600, color #7A84A8, uppercase
  Padding: 12px 16px
  
Table Data Row:
  Background: #151D47
  Border-bottom: 1px solid #1F2948
  Text: size 13px, weight 400, color #A8B0D0
  Padding: 14px 16px
  
  Hover state:
    Background: #1F2948
    Transition: background 100ms ease
    
  Alternate rows (striped):
    Every other row background #0F1535
    
Table Status Indicators:
  Badge (small colored label):
    Padding: 4px 8px
    Border-radius: 3px
    Font-size: 11px
    Font-weight: 600
    
    Green badge: background #00E676, color #0A0E27
    Red badge: background #FF4444, color #FFF
    Yellow badge: background #FFC400, color #0A0E27
    Gray badge: background #3A4556, color #A8B0D0
```

#### Modal/Dialog

```
Modal Overlay:
  Background: rgba(0, 0, 0, 0.7)
  Display: fixed, full screen
  z-index: 1000
  
Modal Container:
  Background: #0F1535
  Border: 1px solid #2A3558
  Border-radius: 8px
  Box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8)
  Max-width: 600px
  Margin: auto
  Padding: 24px
  
Modal Header:
  Font-size: 22px
  Font-weight: 600
  Color: #E8EBF5
  Margin-bottom: 16px
  
Modal Body:
  Font-size: 13px
  Color: #A8B0D0
  Margin-bottom: 20px
  
Modal Footer:
  Border-top: 1px solid #2A3558
  Padding-top: 20px
  Display: flex, gap 8px
  Justify-content: flex-end
```

---

### 1.5 Icons & Symbols

```
Status Icons:
  🟢 Success/Ready: Green circle (#00E676)
  🟡 Warning/Pending: Yellow circle (#FFC400)
  🔴 Error/Critical: Red circle (#FF4444)
  🔵 Info/Neutral: Blue circle (#2196F3)
  ⚪ Unknown/Disabled: Gray circle (#7A84A8)
  ⏸️  Paused: Gray with pause symbol

Direction Indicators:
  ↑ Up/Increase: Green arrow (#00E676)
  ↓ Down/Decrease: Red arrow (#FF4444)
  → Flat/Neutral: Gray arrow (#7A84A8)

Action Icons (18–24px, monochrome):
  Copy, Download, Upload, Share, Expand, Collapse
  Settings, Filter, Sort, Search, Refresh, Close
  Use standard SVG icon set (e.g., Feather Icons, Heroicons)
  Color: #00D4FF (interactive), #7A84A8 (disabled)

Chart Icons:
  📈 Chart Up (growth)
  📉 Chart Down (decline)
  📊 Bar Chart (comparison)
  🎯 Target (goal/metric)
```

---

## Part 2: Page-Level Layouts

### 2.1 Overview Panel Layout

```
┌─────────────────────────────────────────────────────────────┐
│ VEKTOR CONTROL CENTER                 [Settings] [Profile] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ OVERVIEW                                                    │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ KPI TILES (4 columns on desktop, 2 on tablet, 1 mobile) │ │
│ │ ┌──────────────┬──────────────┬──────────────┬────────┐  │ │
│ │ │ NAV          │ Monthly PnL  │ Sharpe Ratio │ Max DD │  │ │
│ │ │ $2,547.3K    │ +$43.2K      │ 1.24         │ -3.2%  │  │ │
│ │ │ ↑ from...    │ +2.1%        │ 30d rolling  │ from   │  │ │
│ │ │              │              │              │ HWM    │  │ │
│ │ └──────────────┴──────────────┴──────────────┴────────┘  │ │
│ │ [spacing: 16px between tiles]                            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ STATUS SUMMARY (3-row grid)                             │ │
│ │                                                         │ │
│ │ Row 1: RUNTIME STATUS                                   │ │
│ │ ✅ Healthy | Orchestrator: ACTIVE | Data pipeline: 100%│ │
│ │ ML models: LOADED | Broker: READY | Agents: 6/6        │ │
│ │                                                         │ │
│ │ Row 2: PORTFOLIO EXPOSURE                               │ │
│ │ 68% deployed | Equities: $1.7M | Cash: $815K           │ │
│ │ Shorts: $127K | Leverage: 1.2x | Max: 1.5x ✅          │ │
│ │                                                         │ │
│ │ Row 3: RISK STATUS                                      │ │
│ │ VaR: $28.4K (65% margin) | Max DD: -3.2% (75% margin) │ │
│ │ Sector concentration: 31% | Limit: 40% ✅              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ALERTS (if any) or EMPTY STATE                          │ │
│ │ ⚠️  2 pending approvals                                 │ │
│ │ 🔵 1 info: Model retraining scheduled                   │ │
│ │ [View all] [Dismiss]                                    │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [View Full P&L] [View Holdings] [Approve Pending] [More]   │
└─────────────────────────────────────────────────────────────┘
```

**CSS Grid Layout** (Tailwind example):
```tsx
// Overview container
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  {/* KPI Tiles - each spans 1 column */}
  {kpiTiles.map(tile => (
    <KPITile key={tile.id} {...tile} />
  ))}
</div>

// Status Summary
<div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-6">
  {/* Each status row */}
  <StatusRow title="RUNTIME STATUS" {...data} />
  <StatusRow title="PORTFOLIO" {...data} />
  <StatusRow title="RISK" {...data} />
</div>
```

### 2.2 Two-Column Layout (Detail View)

Used for Research, Theses, Orders when expanded:

```
Left Column (60% width, list):
┌─────────────────────────┐
│ FILTER/SEARCH           │
│ ┌─────────────────────┐ │
│ │ Item 1 (selected)   │ │
│ └─────────────────────┘ │
│ ┌─────────────────────┐ │
│ │ Item 2              │ │
│ └─────────────────────┘ │
│ ┌─────────────────────┐ │
│ │ Item 3              │ │
│ └─────────────────────┘ │
│ [Load more...]          │
└─────────────────────────┘

Right Column (40% width, detail):
┌──────────────────────────────┐
│ DETAIL PANEL (expanded)       │
│                              │
│ Title                         │
│ ────────────────────────────  │
│ Key info rows                 │
│ └─ metadata                   │
│ └─ metrics                    │
│ └─ actions                    │
│                              │
│ [Action 1] [Action 2]        │
└──────────────────────────────┘
```

**Responsive behavior**:
- Desktop (>1024px): side-by-side, 60/40 split
- Tablet (640–1024px): stacked vertically, full width each
- Mobile (<640px): stacked, full width each

---

### 2.3 Table Layout with Inline Actions

```
┌──────────────────────────────────────────────────────────────┐
│ FILTER ROW                                                   │
│ [Status▼] [Type▼] [Sort▼] [Search___] [Export] [Refresh]   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Summary: "Showing 1–20 of 847 items"                        │
│                                                              │
│ TABLE HEADER                                                 │
│ ┌────┬──────────┬─────────┬──────────┬────────┬─────────────┐
│ │ ID │ TITLE    │ TYPE    │ VALUE    │ PnL    │ ACTIONS     │
│ ├────┼──────────┼─────────┼──────────┼────────┼─────────────┤
│ │ R-1│ Idea 1   │ MACRO   │ 68%      │ +1.2%  │ [•••▼]      │ ← hover reveals menu
│ │    │          │         │          │        │ ├ Details   │
│ │    │          │         │          │        │ ├ Edit      │
│ │    │          │         │          │        │ ├ Archive   │
│ │    │          │         │          │        │ └ Delete    │
│ ├────┼──────────┼─────────┼──────────┼────────┼─────────────┤
│ │ R-2│ Idea 2   │ FUND    │ 54%      │ -0.3%  │ [•••▼]      │
│ └────┴──────────┴─────────┴──────────┴────────┴─────────────┘
│                                                              │
│ PAGINATION                                                   │
│ [< PREV] [NEXT >] | Page 1 of 43 | Jump to: [__] [Go]      │
└──────────────────────────────────────────────────────────────┘
```

**Hover behavior**:
- Row background lightens (#1F2948)
- Actions menu (three-dot) appears on the right
- Entire row is clickable to expand detail

---

## Part 3: Component Library Specs

### 3.1 KPI Tile Component

```jsx
<KPITile 
  title="NAV"
  value={2547320}
  format="currency"
  change={49200}
  changePercent={2.0}
  trend="up"  // "up" | "down" | "flat"
  status="good"  // "good" | "warning" | "critical"
/>

Rendered as:
┌────────────────────────┐
│ NAV                    │
│ $2,547,320             │ (size: 28px, bold)
│ ↑ from $2,498.1K      │ (size: 11px, secondary color)
│ +2.0%                  │ (size: 14px, green)
└────────────────────────┘

CSS:
- Background: #151D47
- Border: 1px solid #2A3558
- Padding: 16px
- Border-radius: 8px
- Cursor: pointer
- Hover: background #1F2948, border #3A4556
```

### 3.2 Status Badge Component

```jsx
<StatusBadge 
  status="approved"  // "approved", "rejected", "pending", "active", "paused"
  label="APPROVED"
/>

Variants:
┌──────────────────────────────────┐
│ 🟢 APPROVED         (green bg)    │
│ 🔴 REJECTED         (red bg)      │
│ 🟡 PENDING          (yellow bg)   │
│ 🟢 ACTIVE           (green bg)    │
│ ⏸️  PAUSED           (gray bg)     │
│ 🔵 INFO             (blue bg)     │
└──────────────────────────────────┘

CSS:
- Padding: 4px 8px
- Border-radius: 3px
- Font-size: 11px
- Font-weight: 600
- Display: inline-block
```

### 3.3 Alert Component

```jsx
<Alert 
  type="warning"  // "warning", "error", "success", "info"
  title="2 Pending Approvals"
  message="Agent discovery requires your sign-off"
  action={{label: "Review", onClick: () => {}}}
/>

Rendered as:
┌─────────────────────────────────────────┐
│ ⚠️  2 PENDING APPROVALS                 │
│ Agent discovery requires your sign-off. │
│ [Review →]                              │
└─────────────────────────────────────────┘

CSS:
- Border-left: 4px solid (color based on type)
- Background: tinted color at 10% opacity
- Padding: 12px 16px
- Margin-bottom: 12px
```

### 3.4 Chart Component (Recharts integration)

```jsx
<SimpleLineChart 
  data={rollingMetrics}
  dataKey="sharpe"
  label="Rolling 30d Sharpe"
  height={200}
  showLegend={false}
/>

Rendered as:
  1.5 ┤     ╱╲
  1.2 ┤   ╱    ╲    ╱────╲
  1.0 ┤  ╱       ╲╱      ╲
  0.8 ┤_╱
      └─────────────────────────
         (30-day rolling line)
```

**Chart rules**:
- Single line per chart (no cluttered multi-lines)
- No gridlines (cleaner)
- Tooltip on hover
- Minimal colors (match theme palette)
- Responsive (responsive container)

---

## Part 4: Interaction Patterns

### 4.1 Filter + Search Pattern

```
┌──────────────────────────────────────────────────────────┐
│ FILTERS & SEARCH                                         │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│ │Status ▼  │ │Type ▼    │ │Sort by ▼ │ │Search _____  │ │
│ │ ACTIVE   │ │ FUND     │ │ NEWEST   │ │_______[X]    │ │
│ └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │
│                                        [Apply] [Reset]   │
└──────────────────────────────────────────────────────────┘

Behavior:
- Dropdowns are sticky (remain selected until changed)
- Search filters in real-time (no submit button needed)
- Apply/Reset buttons only needed if multiple filters can be pending
- Mobile: collapse all dropdowns into single [Filters] button
```

### 4.2 Modal/Approval Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│ CONFIRM ACTION                                          [X]      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Title: "Deploy $200K to Thesis T-12?"                          │
│                                                                 │
│ Context (data the user needs to decide):                        │
│ ├─ Current allocation: $400K | Max: $500K                      │
│ ├─ Would result in: 20% of AUM (at limit)                      │
│ ├─ Risk check: OK (no sector breaches)                          │
│ ├─ Conviction: 68% (agent-estimated)                            │
│                                                                 │
│ Your decision options:                                           │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ☐ Approve                                                   │ │
│ │ ☐ Approve with notes: [__________________________]          │ │
│ │ ☐ Reject                                                    │ │
│ │ ☐ Ask agent for more info                                  │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ [APPROVE] [REJECT] [ASK AGENT]                                │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Expand/Collapse Pattern

```
List row (collapsed):
┌─────────────────────────────────────────────────────────────────┐
│ ► R-47 Fed Pivot   68% ⬆️ 8d live   Risk: OK   [Actions]       │
└─────────────────────────────────────────────────────────────────┘

Click [>] arrow or row to expand:

┌─────────────────────────────────────────────────────────────────┐
│ ▼ R-47 Fed Pivot   68% ⬆️ 8d live   Risk: OK   [Actions]       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ THESIS DETAIL:                                                  │
│ • Source: Research R-47 (OpenClaw macro scan, 2026-05-20)      │
│ • Conviction: 68% (↑ +8% from CPI data)                        │
│ • Allocation: $400K | Max: $500K | Margin: $100K              │
│ • Holdings: BND.US $280K, TMF.US $120K, GOVT.US $80K          │
│ • Exit signal: 65% floor | Current: 68% | Buffer: +3%         │
│                                                                 │
│ SIGNALS BREAKDOWN:                                              │
│ • Fed futures: 50bps cut by Sep (↑ +8%)                        │
│ • CPI data: -0.2% vs expected (↑ +15%)                         │
│ • Sentiment: 87% bullish (↑ +12%)                              │
│ • Payroll data: 190K strong (↓ -8%)                            │
│                                                                 │
│ RECENT UPDATES:                                                 │
│ • 2026-05-23 14:30 | Conviction +8% (Fed speakers)             │
│ • 2026-05-22 11:15 | Created thesis (sentiment shift)          │
│                                                                 │
│ [Edit conviction] [Increase allocation] [Close thesis]         │
│ [View lineage] [View audit trail]                              │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior**:
- Click arrow or row to toggle expand
- Smooth animation (max 300ms)
- Only one row expanded at a time (or allow multiple)
- Expanded content is not cut off by viewport (scroll if needed)

---

## Part 5: Mobile Responsiveness

### 5.1 Breakpoints

```
Mobile: < 640px
  - Single column layout
  - Sidebar collapses to icon-only nav (hamburger menu)
  - Modals/dialogs take full screen minus safe-area
  - Tables become card-stack (each row = collapsed card)
  - Dropdowns become full-width pickers
  
Tablet: 640px – 1024px
  - 2-column layout (when applicable)
  - Sidebar is visible but narrower
  - Tables remain tables (scroll horizontally if needed)
  - KPI tiles: 2 per row (instead of 4)
  
Desktop: 1024px+
  - Full layout as designed
  - 3–4 column grids
  - Sidebar full width
```

### 5.2 Mobile Navigation

```
Desktop (left sidebar):
┌──────┬─────────────────────────────────┐
│VEKTOR│ OVERVIEW                        │
│      │ RESEARCH & DISCOVERY            │
│ ①    │ THESES & POSITIONS              │
│ ②    │ RISK & POLICY                   │
│ ③    │ EXECUTION & ORDERS              │
│ ④    │ AGENTS & RUNTIME                │
│ ⑤    │ APPROVALS & CEO DIGESTS         │
│ ...  │ AUDIT & LINEAGE                 │
└──────┴─────────────────────────────────┘

Mobile (hamburger + bottom nav):
┌──────────────────────────────────────┐
│ ☰ VEKTOR    [Title]      [⚙️] [👤]   │ ← Header
├──────────────────────────────────────┤
│                                      │
│ (main content area)                  │
│                                      │
│                                      │
├──────────────────────────────────────┤
│ 📊 Overview  📚 Research  📈 Risk  ⚙️ │ ← Bottom nav (sticky)
└──────────────────────────────────────┘
```

**Hamburger menu (when tapped)**:
```
┌──────────────────────────────────────┐
│ ✕ NAVIGATION                         │
├──────────────────────────────────────┤
│ 📊 OVERVIEW                          │
│ 📚 RESEARCH & DISCOVERY              │
│ 📈 THESES & POSITIONS                │
│ ⚠️  RISK & POLICY                    │
│ 💰 EXECUTION & ORDERS                │
│ 🤖 AGENTS & RUNTIME                  │
│ ✅ APPROVALS & CEO DIGESTS           │
│ 📋 AUDIT & LINEAGE                   │
│ 🌍 MARKET CONTEXT                    │
│ ⚙️  SETTINGS                         │
│ 🧠 KNOWLEDGE GRAPH                   │
└──────────────────────────────────────┘
```

---

## Part 6: Accessibility Guidelines

### 6.1 WCAG AAA Compliance

```
Color Contrast:
- All text > 4.5:1 ratio (normal text)
- All text > 3:1 ratio (large text, 18px+)
- Test: Use WebAIM contrast checker

Keyboard Navigation:
- Tab order follows visual flow (left-to-right, top-to-bottom)
- All interactive elements tabbable
- Focus indicator: 2px outline in #00D4FF
- Skip links: "Skip to main content"

Screen Reader:
- Semantic HTML: <header>, <nav>, <main>, <section>, <article>
- ARIA labels for icons: aria-label="Close modal"
- Tables: proper <thead>, <tbody>, <th> markup
- Forms: <label> for every input
- Alt text for images (if any)

Focus Management:
- Modal traps focus (can't tab outside)
- After closing modal, focus returns to trigger button
- Loading states have aria-busy="true"
- Error states have aria-invalid="true"
```

### 6.2 Dark Theme Accessibility

```
Dark theme can reduce eye strain BUT:
✅ Ensure sufficient contrast (4.5:1 minimum)
✅ Don't rely solely on color (use icons + color + text)
✅ Provide high-saturation colors for status (not just subtle tints)
✅ Test with users who have color blindness
✅ Provide a light theme option (user preference)
```

---

## Part 7: Performance Guidelines

### 7.1 Load Time Targets

```
First Contentful Paint (FCP): < 1.5s
  - Inline critical CSS
  - Defer non-critical JS
  - Lazy load below-the-fold components

Largest Contentful Paint (LCP): < 2.5s
  - Optimize images (use WebP + fallbacks)
  - Reduce JavaScript
  - Preload critical resources

Cumulative Layout Shift (CLS): < 0.1
  - Avoid unsized images/media
  - Avoid inserting content above existing content
  - Use transform instead of left/top for animations

Time to Interactive (TTI): < 3.8s
  - Code-split JavaScript
  - Remove unused CSS
  - Minify all assets
```

### 7.2 Real-time Data Optimization

```
WebSocket vs REST:
- Use WebSocket for continuous streams (NAV updates, task progress)
- Use REST for discrete queries (search, filters, downloads)

Caching Strategy:
- Browser cache (localStorage) for user preferences
- Service Worker for offline-first static assets
- Redis on backend for hot data (last 100 trades, current positions)

Data Batching:
- Batch multiple small requests into single larger request
- Debounce search input (wait 300ms before sending)
- Throttle scroll events (update charts every 500ms, not every 10ms)

Bundle Optimization:
- Main bundle: < 200KB (gzipped)
- Lazy load heavy features (knowledge graph explorer)
- Tree-shake unused dependencies
```

---

## Conclusion

This design system ensures a **professional, institutional-grade interface** that:
- Minimizes cognitive load (clear hierarchy, consistent patterns)
- Enables fast decision-making (real-time data, deep drill-down on demand)
- Respects operator time (no unnecessary animations, clean typography)
- Scales from mobile to large desktop monitors
- Provides full accessibility (WCAG AAA)

Hand this document to your design/implementation team. All visual decisions are documented.

---

**Document Version**: 1.0  
**Status**: Ready for handoff to engineering  
**Last Updated**: 2026-05-23

