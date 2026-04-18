"""
Live Monitoring and System Status.
Provides startup and runtime diagnostics for fund services.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.config import get_settings
from app.core.context import broker
from app.data.market_data import FEED
from app.fund.agent_runtime import fund_agent_runtime
from app.fund.audit_log import audit_log
from app.fund.decision_ledger import decision_ledger
from app.fund.knowledge_graph import knowledge_graph
from app.fund.orchestrator import firm_orchestrator
from app.fund.realtime_stream import realtime_stream
from app.risk.engine import risk

logger = logging.getLogger("monitoring")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _broker_cash() -> float:
    try:
        if hasattr(broker, "get_cash"):
            return float(broker.get_cash())
        return float(getattr(broker, "cash", 0.0))
    except Exception:
        return 0.0


def _broker_equity() -> float:
    try:
        if hasattr(broker, "get_portfolio_value"):
            return float(broker.get_portfolio_value(FEED.price))
        cash = _broker_cash()
        if hasattr(broker, "positions") and isinstance(getattr(broker, "positions"), dict):
            value = 0.0
            for symbol, pos in broker.positions.items():
                qty = float((pos or {}).get("qty", 0.0))
                value += qty * float(FEED.price(symbol))
            return float(cash + value)
        return float(cash)
    except Exception:
        return _broker_cash()


def _broker_symbols() -> list[str]:
    try:
        if hasattr(broker, "list_symbols"):
            return list(broker.list_symbols())
        if hasattr(broker, "positions") and isinstance(getattr(broker, "positions"), dict):
            return sorted(list(broker.positions.keys()))
    except Exception:
        pass
    return []


def _broker_positions_count() -> int:
    try:
        if hasattr(broker, "list_positions"):
            return len(broker.list_positions(FEED.price))
        return len(_broker_symbols())
    except Exception:
        return 0


class SystemMonitor:
    """Comprehensive system monitoring and status reporting."""

    @staticmethod
    def get_full_status() -> Dict[str, Any]:
        """Get complete system status."""
        try:
            active_tasks = firm_orchestrator.list_active_tasks()
            pending_decisions = firm_orchestrator.list_pending_decisions()
            knowledge_stats = firm_orchestrator.knowledge_stats()

            return {
                "timestamp": _utc_iso(),
                "system": {
                    "version": "5.1.0",
                    "environment": get_settings().ENV,
                    "auto_trading": get_settings().AUTO_TRADING_ENABLED,
                    "agent_runtime": get_settings().AGENT_RUNTIME_ENABLED,
                },
                "fund": {
                    "agent_runtime": {
                        "started": fund_agent_runtime.is_started(),
                        "worker_count": fund_agent_runtime._worker_count
                        if hasattr(fund_agent_runtime, "_worker_count")
                        else 0,
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
                            for t in active_tasks[:5]
                        ],
                    },
                    "knowledge_graph": {
                        "event_count": knowledge_stats.get("event_count", 0),
                        "entity_count": knowledge_stats.get("entity_count", 0),
                        "status": "active",
                    },
                    "decision_ledger": {
                        "total_decisions": len(decision_ledger._ledger)
                        if hasattr(decision_ledger, "_ledger")
                        else 0,
                    },
                    "audit_log": {
                        "total_events": len(audit_log._events) if hasattr(audit_log, "_events") else 0,
                    },
                },
                "broker": {
                    "cash": _broker_cash(),
                    "equity": _broker_equity(),
                    "positions": _broker_positions_count(),
                    "symbols": _broker_symbols(),
                },
                "risk": {
                    "status": risk.status(),
                },
                "realtime_stream": {
                    "subscribers": len(realtime_stream._subscribers)
                    if hasattr(realtime_stream, "_subscribers")
                    else 0,
                },
                "pending_decisions_sample": [
                    {
                        "id": d.get("id"),
                        "type": d.get("type"),
                        "status": d.get("status"),
                        "created_at": str(d.get("created_at")),
                    }
                    for d in pending_decisions[:3]
                ],
            }
        except Exception as exc:
            logger.error("Error getting system status: %s", exc)
            return {"status": "error", "error": str(exc)}

    @staticmethod
    def log_startup_sequence() -> None:
        """Log detailed startup sequence."""
        logger.info("=" * 80)
        logger.info("ALFRED STARTUP SEQUENCE 5.1.0")
        logger.info("=" * 80)
        logger.info("Timestamp: %s", _utc_iso())
        logger.info("Environment: %s", get_settings().ENV)
        logger.info("Agent Runtime: %s", "ENABLED" if get_settings().AGENT_RUNTIME_ENABLED else "DISABLED")
        logger.info("Auto Trading: %s", "ENABLED" if get_settings().AUTO_TRADING_ENABLED else "DISABLED")
        logger.info("-" * 80)

    @staticmethod
    def log_component_status(component: str, status: str, details: str = "") -> None:
        """Log individual component status."""
        status_icon = "OK" if status == "OK" else "WARN" if status == "WARN" else "ERR"
        logger.info("[%s] %-30s %-10s %s", status_icon, component, status, details)

    @staticmethod
    def log_fund_stats() -> None:
        """Log fund system statistics."""
        logger.info("=" * 80)
        logger.info("FUND SYSTEM STATISTICS")
        logger.info("=" * 80)

        try:
            active_tasks = firm_orchestrator.list_active_tasks()
            pending_decisions = firm_orchestrator.list_pending_decisions()
            knowledge_stats = firm_orchestrator.knowledge_stats()

            logger.info("Active Tasks: %s", len(active_tasks))
            logger.info("Pending Decisions: %s", len(pending_decisions))
            logger.info("Knowledge Events: %s", knowledge_stats.get("event_count", 0))
            logger.info("Knowledge Entities: %s", knowledge_stats.get("entity_count", 0))
            logger.info("Broker Cash: $%s", f"{_broker_cash():,.2f}")
            logger.info("Portfolio Equity: $%s", f"{_broker_equity():,.2f}")
            logger.info("Positions: %s", _broker_positions_count())

            if len(active_tasks) > 0:
                logger.info("Recent Active Tasks:")
                for task in active_tasks[:3]:
                    task_id = str(task.get("id") or "")
                    logger.info(" - %s [%s] %s", task.get("type"), task.get("status"), task_id[:16])

            if len(pending_decisions) > 0:
                logger.info("Pending Decisions:")
                for decision in pending_decisions[:3]:
                    did = str(decision.get("id") or "")
                    logger.info(" - %s %s", decision.get("type"), did[:16])

        except Exception as exc:
            logger.error("Error logging fund stats: %s", exc)

        logger.info("=" * 80)


# Initialize monitor
monitor = SystemMonitor()
