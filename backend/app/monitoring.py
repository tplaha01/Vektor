"""
Live Monitoring & System Status
Shows real-time status of all backend components
"""
import logging
from datetime import datetime
from typing import Any, Dict

from app.fund.agent_runtime import fund_agent_runtime
from app.fund.orchestrator import firm_orchestrator
from app.fund.knowledge_graph import knowledge_graph
from app.fund.realtime_stream import realtime_stream
from app.fund.decision_ledger import decision_ledger
from app.fund.audit_log import audit_log
from app.config import get_settings
from app.core.context import broker
from app.data.market_data import FEED
from app.risk.engine import risk

logger = logging.getLogger("monitoring")


class SystemMonitor:
    """Comprehensive system monitoring and status reporting"""

    @staticmethod
    def get_full_status() -> Dict[str, Any]:
        """Get complete system status"""
        try:
            active_tasks = firm_orchestrator.list_active_tasks()
            pending_decisions = firm_orchestrator.list_pending_decisions()
            knowledge_stats = firm_orchestrator.knowledge_stats()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "system": {
                    "version": "5.1.0",
                    "environment": get_settings().ENV,
                    "auto_trading": get_settings().AUTO_TRADING_ENABLED,
                    "agent_runtime": get_settings().AGENT_RUNTIME_ENABLED,
                },
                "fund": {
                    "agent_runtime": {
                        "started": fund_agent_runtime.is_started(),
                        "worker_count": fund_agent_runtime._worker_count if hasattr(fund_agent_runtime, '_worker_count') else 0,
                        "status": "running" if fund_agent_runtime.is_started() else "stopped",
                    },
                    "orchestrator": {
                        "active_tasks": len(active_tasks),
                        "pending_decisions": len(pending_decisions),
                        "active_task_list": [
                            {
                                "id": t.get("id"),
                                "type": t.get("type"),
                                "status": t.get("status"),
                                "created_at": str(t.get("created_at")),
                            }
                            for t in active_tasks[:5]  # Show last 5
                        ],
                    },
                    "knowledge_graph": {
                        "event_count": knowledge_stats.get("event_count", 0),
                        "entity_count": knowledge_stats.get("entity_count", 0),
                        "status": "active",
                    },
                    "decision_ledger": {
                        "total_decisions": len(decision_ledger._ledger) if hasattr(decision_ledger, '_ledger') else 0,
                    },
                    "audit_log": {
                        "total_events": len(audit_log._events) if hasattr(audit_log, '_events') else 0,
                    },
                },
                "broker": {
                    "cash": float(broker.get_cash()),
                    "equity": float(broker.get_portfolio_value(FEED.price)),
                    "positions": len(broker.list_positions(FEED.price)),
                    "symbols": list(broker.list_symbols()),
                },
                "risk": {
                    "status": risk.status(),
                },
                "realtime_stream": {
                    "subscribers": len(realtime_stream._subscribers) if hasattr(realtime_stream, '_subscribers') else 0,
                },
                "pending_decisions_sample": [
                    {
                        "id": d.get("id"),
                        "type": d.get("type"),
                        "status": d.get("status"),
                        "created_at": str(d.get("created_at")),
                    }
                    for d in pending_decisions[:3]  # Show last 3
                ],
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"status": "error", "error": str(e)}

    @staticmethod
    def log_startup_sequence():
        """Log detailed startup sequence"""
        logger.info("=" * 80)
        logger.info("🚀 ALFRED STARTUP SEQUENCE 5.1.0")
        logger.info("=" * 80)
        logger.info(f"⏰ Timestamp: {datetime.utcnow().isoformat()}")
        logger.info(f"🌍 Environment: {get_settings().ENV}")
        logger.info(f"🤖 Agent Runtime: {'ENABLED' if get_settings().AGENT_RUNTIME_ENABLED else 'DISABLED'}")
        logger.info(f"📊 Auto Trading: {'ENABLED' if get_settings().AUTO_TRADING_ENABLED else 'DISABLED'}")
        logger.info("-" * 80)

    @staticmethod
    def log_component_status(component: str, status: str, details: str = ""):
        """Log individual component status"""
        status_icon = "✅" if status == "OK" else "⚠️" if status == "WARN" else "❌"
        logger.info(f"{status_icon} {component:<30} {status:<10} {details}")

    @staticmethod
    def log_fund_stats():
        """Log fund system statistics"""
        logger.info("=" * 80)
        logger.info("📈 FUND SYSTEM STATISTICS")
        logger.info("=" * 80)
        
        try:
            active_tasks = firm_orchestrator.list_active_tasks()
            pending_decisions = firm_orchestrator.list_pending_decisions()
            knowledge_stats = firm_orchestrator.knowledge_stats()
            
            logger.info(f"🎯 Active Tasks: {len(active_tasks)}")
            logger.info(f"📋 Pending Decisions: {len(pending_decisions)}")
            logger.info(f"📚 Knowledge Events: {knowledge_stats.get('event_count', 0)}")
            logger.info(f"🏷️  Knowledge Entities: {knowledge_stats.get('entity_count', 0)}")
            logger.info(f"💰 Broker Cash: ${float(broker.get_cash()):,.2f}")
            logger.info(f"📊 Portfolio Equity: ${float(broker.get_portfolio_value(FEED.price)):,.2f}")
            logger.info(f"📍 Positions: {len(broker.list_positions(FEED.price))}")
            
            if len(active_tasks) > 0:
                logger.info(f"\n🔄 Recent Active Tasks:")
                for task in active_tasks[:3]:
                    logger.info(f"   └─ {task.get('type')} [{task.get('status')}] - {task.get('id')[:16]}...")
            
            if len(pending_decisions) > 0:
                logger.info(f"\n⏳ Pending Decisions:")
                for decision in pending_decisions[:3]:
                    logger.info(f"   └─ {decision.get('type')} - {decision.get('id')[:16]}...")
        
        except Exception as e:
            logger.error(f"Error logging fund stats: {e}")
        
        logger.info("=" * 80)


# Initialize monitor
monitor = SystemMonitor()
