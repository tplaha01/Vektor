# Admin Console & Research Publication Page - Integration Guide

## Overview

This guide provides step-by-step instructions for integrating the production-level Admin Console and Blog/Research Publication pages into the Viktor trading platform.

## Directory Structure Created

### Frontend Components

```
frontend/src/
├── pages/
│   ├── Admin.jsx                 # Main admin dashboard
│   └── Research.jsx              # Research & blog hub
├── components/
│   ├── admin/
│   │   ├── KPIGrid.jsx          # Key performance indicator cards
│   │   ├── AgentMonitor.jsx     # Agent worker pool monitor
│   │   ├── DecisionQueue.jsx    # Pending decision approvals
│   │   ├── RiskGauges.jsx       # Risk limits & sleeve allocation
│   │   ├── AuditTimeline.jsx    # Transaction audit trail
│   │   └── PositionsPanel.jsx   # Portfolio holdings
│   └── research/
│       ├── ResearchGrid.jsx     # Research card grid
│       ├── ResearchDetail.jsx   # Detailed research view
│       └── ProvenanceVisualization.jsx  # Lineage tree
└── styles/
    ├── admin.css                # Admin console dark theme
    └── research.css             # Research page dark theme
```

### Backend API

```
backend/app/
└── admin_research_routes.py      # FastAPI routes for admin & research
```

## Integration Steps

### 1. Frontend Router Setup

Add these routes to your frontend routing configuration (e.g., `src/App.jsx` or router config):

```jsx
import Admin from './pages/Admin';
import Research from './pages/Research';

// Add to your route definitions:
{
  path: '/admin',
  component: Admin,
  protected: true,  // Require authentication
  layout: 'minimal' // No side navigation, full width
},
{
  path: '/research',
  component: Research,
  layout: 'minimal'
},
{
  path: '/blog',
  component: Research,
  layout: 'minimal'
}
```

### 2. Backend Integration

Add the new routes to your FastAPI main application:

```python
# In backend/app/main.py

from admin_research_routes import router as admin_router, research_router

# Include routers
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(research_router, prefix="/research", tags=["research"])

# OR if using blueprint pattern:
# from app.admin_research_routes import router as admin_router
# app.include_router(admin_router)
```

### 3. Update Import Dependencies

Ensure all required packages are installed:

```bash
# Frontend dependencies (should already be present)
npm ls react lucide-react recharts  # All should be >=1.0

# Backend dependencies (FastAPI already installed)
pip list | grep -E "fastapi|pydantic|uvicorn"
```

### 4. CSS Integration

The CSS files use CSS variables defined in `:root`. Make sure your main stylesheet or HTML file doesn't conflict:

```css
/* frontend/src/styles/admin.css */
/* frontend/src/styles/research.css */
/* Both use dark theme CSS variables - no conflicts with existing styles */
```

If using Tailwind CSS, the component CSS is written with vanilla CSS and won't interfere.

### 5. Database Schema Extensions (Optional but Recommended)

If integrating with persistence, add support for:

```python
# Models for research reports
class ResearchReport(SQLModel, table=True):
    report_id: str = Field(primary_key=True)
    agent_id: str
    agent_role: str
    title: str
    summary: str
    findings: List[str]  # JSON array
    asset_universe: List[str]
    confidence: float
    created_at: datetime
    published_at: datetime
    status: str
    views: int = 0
    provenance: dict  # JSON object

# Models for audit events
class AuditEvent(SQLModel, table=True):
    event_id: str = Field(primary_key=True)
    timestamp: datetime
    event_type: str
    details: dict
    order_id: Optional[str]
    decision_id: Optional[str]
```

### 6. WebSocket Integration (Real-time Updates)

For real-time admin dashboard updates, connect WebSocket:

```javascript
// In AdminDashboard useEffect:
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8000/ws');
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'metrics_update') {
      setMetrics(data.payload);
    }
  };
  
  return () => ws.close();
}, []);
```

### 7. API Response Mapping

The components expect specific API response formats. Ensure your endpoints return:

**For `/admin/metrics/summary`:**
```json
{
  "total_equity": 1000000,
  "equity_change": 2.5,
  "realized_pnl": 15000,
  "current_drawdown": 2.3,
  "active_positions": 12,
  "win_rate": 0.62,
  "sharpe_ratio": 1.45
}
```

**For `/fund/research/reports`:**
```json
{
  "reports": [
    {
      "report_id": "uuid",
      "agent_id": "agent_id",
      "agent_role": "research_director",
      "title": "Report Title",
      "summary": "Summary text",
      "findings": ["finding1", "finding2"],
      "asset_universe": ["AAPL", "MSFT"],
      "confidence": 0.78,
      "published_at": "2024-01-15T10:30:00",
      "status": "published",
      "provenance": {
        "data_sources": ["source1"],
        "thesis_id": "thesis_id",
        "decision_ids": ["dec1"],
        "policy_gates_applied": ["gate1"]
      }
    }
  ]
}
```

## Feature Breakdown

### Admin Console

**Dashboard Tab:**
- KPI grid showing equity, P&L, drawdown, win rate, Sharpe
- Agent worker pool with task distribution
- Decision queue for manual trade approvals
- Risk gauges with sleeve allocation visualization

**Agents Tab:**
- Detailed worker pool with success rates
- Active task queue with priority levels
- Worker uptime and performance metrics

**Decisions Tab:**
- Expandable decision cards with full context
- Quick approve/reject buttons
- Audit trail links for provenance

**Risk Control Tab:**
- Drawdown gauge with threshold alerts
- Sleeve allocation progress bars
- Policy compliance status checks

**Positions Tab:**
- Real-time portfolio holdings table
- P&L tracking and allocation percentage
- Quick close position buttons

**Audit Log Tab:**
- Immutable event timeline
- Expandable event details with full provenance
- Filter by event type, date range

**Settings Tab:**
- Model routing configuration
- Incident controls (halt trading, pause agents)
- Runtime configuration parameters

### Research Publication Page

**Grid View:**
- Responsive card layout (3+ columns on desktop)
- Confidence badges (high/medium/low)
- Asset universe tags
- Author cards with agent roles
- Publication dates and view counts

**Search & Filter:**
- Full-text search (title, summary, assets)
- Status filter (all/published/draft)
- Sort options (recent/confidence/trending)

**Detail View:**
- Full report with executive summary
- Key findings in numbered list
- Asset universe listing
- Author profile with metadata
- Provenance visualization (SVG tree)
- Data source attribution
- Linked decisions and trading thesis

## Performance Considerations

1. **Dashboard Polling:** Default 10-second refresh interval (configurable)
2. **Research Caching:** ISR (incremental static regeneration) for Next.js landing page
3. **Grid Virtualization:** Large tables use virtualization for <50ms scroll
4. **API Pagination:** All list endpoints paginate with limit/offset

## Security & Access Control

1. **Admin Console:** Requires authentication + `admin` role
2. **Research Pages:** Public research can be published separately
3. **Decision Approvals:** Requires explicit approval with audit logging
4. **API Rate Limiting:** Recommended 100 req/min per user

## Styling Customization

All colors use CSS variables (can be overridden):

```css
:root {
  --bg0: #060608;      /* Main background */
  --purple: #9b7fe8;   /* Primary accent */
  --green: #3ecf8e;    /* Success color */
  --red: #e05252;      /* Error color */
  /* ... see admin.css and research.css for full list */
}
```

## Testing Checklist

- [ ] Admin page loads without authentication redirect
- [ ] KPI metrics update every 10 seconds
- [ ] Decision approve/reject buttons work
- [ ] Research cards click through to detail view
- [ ] Provenance tree renders SVG correctly
- [ ] Mobile responsive on 480px screens
- [ ] Dark theme contrast meets WCAG AA standards
- [ ] API responses handle empty states gracefully
- [ ] WebSocket connections establish properly
- [ ] Sidebar navigation works on mobile

## Troubleshooting

**Admin metrics not loading:**
- Check `/admin/metrics/summary` endpoint returns valid data
- Verify CORS headers allow frontend domain
- Check browser console for network errors

**Research reports empty:**
- Ensure `/fund/research/reports` endpoint is working
- Check API response format matches expected schema
- Verify agent_role values match roleMap in ResearchGrid.jsx

**Styling issues:**
- Confirm CSS variables are defined in `:root`
- Check for CSS specificity conflicts with existing styles
- Verify Tailwind CSS purge doesn't remove component classes

**Mobile layout broken:**
- Check media queries at 768px and 480px breakpoints
- Verify sidebar overlay appears on mobile
- Test touch interactions on actual mobile device

## Next Steps

1. **Implement Mock Data:** Replace mock data in routes with real fund data
2. **Add WebSocket Updates:** Real-time metric streaming for dashboard
3. **Research Publishing Workflow:** Agent report creation pipeline
4. **Sentiment Dashboard:** Real-time sentiment integration
5. **Investor Portal:** Separate authenticated LP-facing pages
6. **Analytics Enhancement:** Richer attribution and performance analysis

## API Endpoint Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/admin/metrics/summary` | Dashboard KPIs |
| GET | `/admin/agents/workers/status` | Worker pool status |
| GET | `/admin/agents/tasks/active` | Active tasks |
| GET | `/admin/decisions/pending` | Pending decisions |
| POST | `/admin/decisions/{id}/approve` | Approve decision |
| POST | `/admin/decisions/{id}/reject` | Reject decision |
| GET | `/admin/sleeves/budgets` | Sleeve allocations |
| GET | `/admin/audit/orders/{id}/timeline` | Audit trail |
| GET | `/research/reports` | List research |
| GET | `/research/reports/{id}` | Report detail |
| POST | `/research/reports` | Publish report |
| GET | `/research/sentiment/current` | Real-time sentiment |
| GET | `/research/sentiment/history/{symbol}` | Sentiment history |

## Support & Questions

For implementation support:
1. Review Viktor.md for system architecture
2. Check DevViktor.md for development rules
3. Consult existing codebase patterns in backend/app/
4. Test in isolation before merging to main branch
