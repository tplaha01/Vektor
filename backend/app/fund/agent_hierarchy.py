"""
Agent Orchestration Hierarchy
Defines the organizational structure of agents and exposes real-time status.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, List
from threading import RLock
from datetime import datetime, timezone


def _utc_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


AgentRole = Literal[
    "fund_manager",
    "research_director",
    "trading_director",
    "risk_auditor",
    "compliance_ops",
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_timeseries_analyst",
    "insight_researcher",
    "hedge_fund_researcher",
    "blog_writer",
]


@dataclass
class AgentStatus:
    """Status of a single agent."""
    agent_id: str
    role: AgentRole
    status: Literal["running", "idle", "error", "stopped"]
    current_task: str | None = None
    current_activity: str | None = None
    last_task_id: str | None = None
    last_task_status: str | None = None
    last_error: str | None = None
    task_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    last_heartbeat: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "status": self.status,
            "current_task": self.current_task,
            "current_activity": self.current_activity,
            "last_task_id": self.last_task_id,
            "last_task_status": self.last_task_status,
            "last_error": self.last_error,
            "task_count": self.task_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "blocked_count": self.blocked_count,
            "last_heartbeat": self.last_heartbeat,
        }


class AgentHierarchy:
    """
    Organizational hierarchy of agents in the fund.
    
    Structure:
    - Fund Manager (top level, orchestrates all decisions)
      ├─ Research Director (coordinates research tasks)
      │  ├─ Technical Analyst (analyst role)
      │  ├─ Fundamental Analyst (analyst role)
      │  ├─ Sentiment Analyst (analyst role)
      │  ├─ ML Timeseries Analyst (analyst role)
      │  ├─ Insight Researcher (analyst role)
      │  └─ Hedge Fund Researcher (analyst role)
      ├─ Trading Director (executes trades)
      ├─ Risk Auditor (independent risk control)
      └─ Compliance Ops (policy enforcement)
    """
    
    def __init__(self):
        self._lock = RLock()
        self._agent_status: Dict[str, AgentStatus] = {}
        self._init_hierarchy()
    
    def _init_hierarchy(self):
        """Initialize default hierarchy."""
        # Executive tier
        roles_to_init = {
            "fund_manager": "Fund Manager",
            "research_director": "Research Director",
            "trading_director": "Trading Director",
            "risk_auditor": "Risk Auditor",
            "compliance_ops": "Compliance Ops",
            # Analyst tier
            "technical_analyst": "Technical Analyst",
            "fundamental_analyst": "Fundamental Analyst",
            "sentiment_analyst": "Sentiment Analyst",
            "ml_timeseries_analyst": "ML Timeseries Analyst",
            "insight_researcher": "Insight Researcher",
            "hedge_fund_researcher": "Hedge Fund Researcher",
            # Support tier
            "blog_writer": "Blog Writer",
        }
        
        with self._lock:
            for role, display_name in roles_to_init.items():
                agent_id = f"agent-{role}"
                self._agent_status[agent_id] = AgentStatus(
                    agent_id=agent_id,
                    role=role,  # type: ignore
                    status="stopped",
                    last_heartbeat=_utc_iso(),
                )
    
    def update_agent_status(
        self,
        agent_id: str,
        role: AgentRole,
        status: Literal["running", "idle", "error", "stopped"],
        current_task: str | None = None,
        current_activity: str | None = None,
        last_task_id: str | None = None,
        last_task_status: str | None = None,
        last_error: str | None = None,
        task_count: int = 0,
        success_count: int = 0,
        failed_count: int = 0,
        blocked_count: int = 0,
    ):
        """Update agent status."""
        with self._lock:
            self._agent_status[agent_id] = AgentStatus(
                agent_id=agent_id,
                role=role,
                status=status,
                current_task=current_task,
                current_activity=current_activity,
                last_task_id=last_task_id,
                last_task_status=last_task_status,
                last_error=last_error,
                task_count=task_count,
                success_count=success_count,
                failed_count=failed_count,
                blocked_count=blocked_count,
                last_heartbeat=_utc_iso(),
            )
    
    def get_agent_status(self, agent_id: str) -> AgentStatus | None:
        """Get status of a single agent."""
        with self._lock:
            return self._agent_status.get(agent_id)
    
    def get_all_agents(self) -> List[AgentStatus]:
        """Get all agents."""
        with self._lock:
            return list(self._agent_status.values())
    
    def get_hierarchy_view(self) -> dict[str, Any]:
        """
        Get hierarchy organized view suitable for visualization.
        
        Returns:
        {
            "fund_manager": {...},
            "executives": [
                {"research_director": {...}, "analysts": [...]},
                {"trading_director": {...}},
                ...
            ],
            "support": [...]
        }
        """
        with self._lock:
            # Get agent statuses
            all_agents = {agent.role: agent for agent in self._agent_status.values()}
            
            # Build hierarchy
            hierarchy = {
                "fund_manager": all_agents.get("fund_manager", {}).to_dict() if "fund_manager" in all_agents else None,
                "executives": [
                    {
                        "research_director": all_agents.get("research_director", {}).to_dict() if "research_director" in all_agents else None,
                        "analysts": [
                            all_agents.get("technical_analyst", {}).to_dict() if "technical_analyst" in all_agents else None,
                            all_agents.get("fundamental_analyst", {}).to_dict() if "fundamental_analyst" in all_agents else None,
                            all_agents.get("sentiment_analyst", {}).to_dict() if "sentiment_analyst" in all_agents else None,
                            all_agents.get("ml_timeseries_analyst", {}).to_dict() if "ml_timeseries_analyst" in all_agents else None,
                            all_agents.get("insight_researcher", {}).to_dict() if "insight_researcher" in all_agents else None,
                            all_agents.get("hedge_fund_researcher", {}).to_dict() if "hedge_fund_researcher" in all_agents else None,
                        ]
                    },
                    {
                        "trading_director": all_agents.get("trading_director", {}).to_dict() if "trading_director" in all_agents else None,
                    },
                    {
                        "risk_auditor": all_agents.get("risk_auditor", {}).to_dict() if "risk_auditor" in all_agents else None,
                    },
                    {
                        "compliance_ops": all_agents.get("compliance_ops", {}).to_dict() if "compliance_ops" in all_agents else None,
                    }
                ],
                "support": [
                    all_agents.get("blog_writer", {}).to_dict() if "blog_writer" in all_agents else None,
                ],
                "timestamp": _utc_iso(),
            }
            
            return hierarchy
    
    def get_active_agents(self) -> List[AgentStatus]:
        """Get all agents with running status."""
        with self._lock:
            return [agent for agent in self._agent_status.values() if agent.status == "running"]
    
    def get_idle_agents(self) -> List[AgentStatus]:
        """Get all agents with idle status."""
        with self._lock:
            return [agent for agent in self._agent_status.values() if agent.status == "idle"]
    
    def get_error_agents(self) -> List[AgentStatus]:
        """Get all agents with error status."""
        with self._lock:
            return [agent for agent in self._agent_status.values() if agent.status == "error"]
    
    def get_hierarchy_stats(self) -> dict[str, Any]:
        """Get statistics about the hierarchy."""
        with self._lock:
            all_agents = list(self._agent_status.values())
            active = [a for a in all_agents if a.status == "running"]
            idle = [a for a in all_agents if a.status == "idle"]
            error = [a for a in all_agents if a.status == "error"]
            stopped = [a for a in all_agents if a.status == "stopped"]
            
            return {
                "total_agents": len(all_agents),
                "active_count": len(active),
                "idle_count": len(idle),
                "error_count": len(error),
                "stopped_count": len(stopped),
                "active_roles": [a.role for a in active],
                "idle_roles": [a.role for a in idle],
                "error_roles": [a.role for a in error],
                "timestamp": _utc_iso(),
            }


# Singleton instance
agent_hierarchy = AgentHierarchy()
