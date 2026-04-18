"""
Monitoring Routes - Real-time system status endpoints
Access these endpoints to monitor the backend live
"""
from typing import Any, Dict
from fastapi import APIRouter
from app.monitoring import monitor

router = APIRouter(prefix="/api/monitor", tags=["monitoring"])


@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """
    Get complete system status snapshot
    
    Returns:
    - Fund system: agents, tasks, decisions, knowledge graph
    - Broker: positions, cash, equity
    - Risk: current risk metrics
    - Realtime: active subscribers
    """
    return monitor.get_full_status()


@router.get("/agents")
async def get_agents_status() -> Dict[str, Any]:
    """Get detailed agent runtime status"""
    from app.fund.agent_runtime import fund_agent_runtime
    
    return {
        "started": fund_agent_runtime.is_started(),
        "status": "running" if fund_agent_runtime.is_started() else "stopped",
        "details": "Agent runtime manages research, analysis, and trading decisions",
    }


@router.get("/agents/hierarchy")
async def get_agent_hierarchy() -> Dict[str, Any]:
    """Get agent organizational hierarchy and real-time status.
    
    Returns hierarchical view of all agents with their current status,
    current tasks, and activity information. This is the primary endpoint
    for building system overview visualizations.
    """
    from app.fund.agent_hierarchy import agent_hierarchy
    
    return {
        "hierarchy": agent_hierarchy.get_hierarchy_view(),
        "stats": agent_hierarchy.get_hierarchy_stats(),
    }


@router.get("/agents/hierarchy/stats")
async def get_agent_hierarchy_stats() -> Dict[str, Any]:
    """Get statistics about agent hierarchy (active, idle, error counts)."""
    from app.fund.agent_hierarchy import agent_hierarchy
    
    return agent_hierarchy.get_hierarchy_stats()


@router.get("/tasks")
async def get_active_tasks() -> Dict[str, Any]:
    """Get all active fund tasks"""
    from app.fund.orchestrator import firm_orchestrator
    
    active_tasks = firm_orchestrator.list_active_tasks()
    return {
        "count": len(active_tasks),
        "tasks": active_tasks,
    }


@router.get("/decisions")
async def get_pending_decisions() -> Dict[str, Any]:
    """Get all pending trade/allocation decisions"""
    from app.fund.orchestrator import firm_orchestrator
    
    pending = firm_orchestrator.list_pending_decisions()
    return {
        "count": len(pending),
        "decisions": pending,
    }


@router.get("/knowledge")
async def get_knowledge_graph_stats() -> Dict[str, Any]:
    """Get knowledge graph statistics and recent events"""
    from app.fund.orchestrator import firm_orchestrator
    from app.fund.knowledge_graph import knowledge_graph
    
    stats = firm_orchestrator.knowledge_stats()
    
    # Try to get recent events from knowledge graph
    recent_events = []
    try:
        if hasattr(knowledge_graph, '_events'):
            recent_events = list(knowledge_graph._events)[-10:]
    except:
        pass
    
    return {
        "event_count": stats.get("event_count", 0),
        "entity_count": stats.get("entity_count", 0),
        "recent_events": recent_events[:5] if recent_events else [],
    }


@router.get("/broker")
async def get_broker_status() -> Dict[str, Any]:
    """Get broker/paper trading status"""
    from app.core.context import broker
    from app.data.market_data import FEED
    
    positions = broker.list_positions(FEED.price)
    
    return {
        "cash": float(broker.get_cash()),
        "portfolio_value": float(broker.get_portfolio_value(FEED.price)),
        "positions_count": len(positions),
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "entry_price": float(p.entry_price),
                "current_price": FEED.price(p.symbol),
                "unrealized_pnl": float(p.unrealized_pnl(FEED.price)),
            }
            for p in positions
        ],
        "orders_count": len(broker.list_orders()),
    }


@router.get("/health-detailed")
async def detailed_health() -> Dict[str, Any]:
    """Detailed health check with all component status"""
    from app.ml.alpha_model import model_status
    from app.utils.sentiment import sentiment_model_name
    from app.risk.engine import risk
    from app.websocket.stream import manager, WATCHLIST
    
    status_report = monitor.get_full_status()
    status_report["components"] = {
        "ml_model": model_status(),
        "sentiment_model": sentiment_model_name(),
        "risk_engine": risk.status(),
        "websocket_clients": len(manager.active),
        "watchlist": WATCHLIST,
    }
    
    return status_report
