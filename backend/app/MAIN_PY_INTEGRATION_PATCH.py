"""
Integration patch for backend/app/main.py

This file shows how to integrate the new admin and research routers into the main FastAPI application.

Add these lines to your backend/app/main.py file:
"""

# ====================================================================
# ADD TO IMPORTS (around line 11-12, after other route imports)
# ====================================================================

# from app.admin_research_routes import router as admin_router
# from app.admin_research_routes import research_router as research_api_router

# ====================================================================
# ADD ROUTER INCLUDES (around line 56, after existing routers)
# ====================================================================

# app.include_router(admin_router, prefix="/admin", tags=["admin"])
# app.include_router(research_api_router, prefix="/research", tags=["research"])

# ====================================================================
# COMPLETE UPDATED SECTION (for reference)
# ====================================================================
"""
The updated import section should look like:

from app.fund.router import router as fund_router
from app.fund.orchestrator import firm_orchestrator
from app.admin_research_routes import router as admin_router
from app.admin_research_routes import research_router as research_api_router  # Renamed to avoid conflict

...

The updated router inclusion section should look like:

app.include_router(backtest_router)
app.include_router(fund_router)
app.include_router(admin_router)
app.include_router(research_api_router)
"""

# ====================================================================
# OPTIONAL: Update _PUBLIC_PATHS if needed
# ====================================================================
"""
If you want to allow certain admin endpoints without API key authentication during dev:

_PUBLIC_PATHS = {
    "/health",
    "/ws",
    "/docs",
    "/openapi.json",
    "/redoc",
    # Uncomment for development only - require API key in production
    # "/admin/metrics/summary",
    # "/research/reports",
}
"""

# ====================================================================
# EXAMPLE: How to use in your app
# ====================================================================
"""
After integration, your endpoints will be accessible:

Admin Dashboard:
- GET  /admin/metrics/summary
- GET  /admin/agents/workers/status
- GET  /admin/agents/tasks/active
- GET  /admin/decisions/pending
- POST /admin/decisions/{id}/approve
- POST /admin/decisions/{id}/reject
- GET  /admin/sleeves/budgets
- GET  /admin/audit/orders/{id}/timeline

Research API:
- GET  /research/reports
- GET  /research/reports/{id}
- POST /research/reports
- GET  /research/sentiment/current
- GET  /research/sentiment/history/{symbol}
"""
