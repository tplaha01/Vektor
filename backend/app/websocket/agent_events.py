"""
WebSocket streaming for agent orchestration events.
Real-time visibility into agent status, tasks, decisions, and orchestration flow.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from threading import RLock, Thread
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("alfred.websocket.agent_events")

# Global reference to the main event loop for cross-thread scheduling
_main_event_loop: asyncio.AbstractEventLoop | None = None


def _utc_iso() -> str:
    """Return current UTC time in ISO 8601 format with Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class AgentEventStreamManager:
    """
    Manages WebSocket connections and broadcasts agent orchestration events.
    
    Event types:
    - agent.status_changed: Agent transitioned state (idle→running→completed)
    - agent.task_started: New task dispatched to agent
    - agent.task_completed: Task finished (success/error)
    - agent.error: Agent error occurred
    - orchestration.signal_pack_created: New analyst swarm launched
    - orchestration.signal_pack_completed: Analyst swarm finished
    - orchestration.decision_made: Fund manager made decision
    - orchestration.trade_executed: Trade executor completed order
    """
    
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self._lock = RLock()
        self._event_buffer: list[dict[str, Any]] = []
        self._max_buffer = 1000
        self._seq = 0
        self._event_loop: asyncio.AbstractEventLoop | None = None
        
        # Agent status cache for new connections
        self._agent_status_cache: Dict[str, dict] = {}
    
    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store reference to main event loop for cross-thread scheduling."""
        self._event_loop = loop
        logger.debug(f"Agent event stream loop set: {loop}")
    
    async def connect(self, ws: WebSocket):
        """Accept connection and send cached agent status."""
        await ws.accept()
        with self._lock:
            self.active.add(ws)
        
        # Send initial agent status snapshot to new client
        try:
            initial_state = {
                "type": "agent.status_snapshot",
                "timestamp": _utc_iso(),
                "agents": dict(self._agent_status_cache),
            }
            await ws.send_json(initial_state)
            logger.info(f"Agent stream connected; sent status snapshot with {len(self._agent_status_cache)} agents")
        except Exception as e:
            logger.warning(f"Failed to send initial snapshot: {e}")
            await self.disconnect(ws)
    
    async def disconnect(self, ws: WebSocket):
        """Remove connection from active set."""
        with self._lock:
            self.active.discard(ws)
    
    async def broadcast(self, event: dict[str, Any]):
        """Broadcast event to all connected clients."""
        if not self.active:
            return
        
        with self._lock:
            # Add to buffer
            self._seq += 1
            event["event_id"] = f"ae-{self._seq:08d}"
            event["timestamp"] = _utc_iso()
            self._event_buffer.append(event)
            if len(self._event_buffer) > self._max_buffer:
                self._event_buffer = self._event_buffer[-self._max_buffer:]
        
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        
        for d in dead:
            await self.disconnect(d)
    
    def update_agent_status(self, agent_id: str, status: dict[str, Any]):
        """Update cached agent status (called from sync context)."""
        with self._lock:
            self._agent_status_cache[agent_id] = {
                "agent_id": agent_id,
                "last_updated": _utc_iso(),
                **status,
            }
    
    def get_agent_status_snapshot(self) -> dict[str, Any]:
        """Get current agent status snapshot."""
        with self._lock:
            return {
                "type": "agent.status_snapshot",
                "timestamp": _utc_iso(),
                "agents": dict(self._agent_status_cache),
            }
    
    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent events from buffer."""
        with self._lock:
            return list(self._event_buffer[-max(1, limit):])


# Singleton instance
agent_event_stream = AgentEventStreamManager()


def publish_agent_event(event_type: str, data: dict[str, Any]) -> None:
    """
    Publish agent event to stream (thread-safe, non-blocking).
    
    Args:
        event_type: Event type (e.g., 'agent.status_changed', 'orchestration.decision_made')
        data: Event payload
    """
    event = {
        "type": event_type,
        "data": data,
    }
    
    # Add to buffer synchronously
    with agent_event_stream._lock:
        agent_event_stream._seq += 1
        event["event_id"] = f"ae-{agent_event_stream._seq:08d}"
        event["timestamp"] = _utc_iso()
        agent_event_stream._event_buffer.append(event)
        if len(agent_event_stream._event_buffer) > agent_event_stream._max_buffer:
            agent_event_stream._event_buffer = agent_event_stream._event_buffer[-agent_event_stream._max_buffer:]
    
    # Broadcast asynchronously (don't block caller)
    if agent_event_stream._event_loop:
        try:
            asyncio.run_coroutine_threadsafe(
                agent_event_stream.broadcast(event),
                agent_event_stream._event_loop
            )
        except Exception as e:
            logger.warning(f"Failed to schedule broadcast: {e}")
    else:
        logger.debug("No event loop available for broadcast (startup phase?)")
