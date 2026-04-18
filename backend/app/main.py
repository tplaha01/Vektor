from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.context import broker
from app.models import SignalRequest, OrderIn
from app.strategies.hybrid import hybrid_signal
from app.data.news import latest_news
from app.analytics import build_metrics_from_broker
from app.websocket.stream import manager, stream_loop, WATCHLIST
from app.websocket.agent_events import agent_event_stream, publish_agent_event
from app.data.market_data import FEED
from app.risk.engine import risk
from app.backtest.router import router as backtest_router
from app.config import get_settings
from app.fund.agent_runtime import fund_agent_runtime
from app.fund.knowledge_graph import knowledge_graph
from app.fund.openclaw_command_adapter import openclaw_command_adapter
from app.fund.router import router as fund_router
from app.fund.orchestrator import firm_orchestrator
from app.fund.runtime_guard import data_integrity_guard
from app.fund.realtime_stream import realtime_stream
from app.admin_research_routes import router as admin_router
from app.admin_research_routes import research_router
from app.admin_research_routes import blog_router
from app.monitoring_routes import router as monitoring_router
from app.knowledge_routes import router as knowledge_router
from app.devlog import get_dev_logger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("trading_bot.log"),
    ],
)
logger = logging.getLogger("alfred")

settings = get_settings()

app = FastAPI(title="Hybrid Trading Bot", version="5.1.0")

# Development session tracking
_current_dev_session = None

_ALLOWED_ORIGINS = [
    "http://localhost:9000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:9000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
_frontend_url = os.getenv("FRONTEND_URL")
if _frontend_url:
    _ALLOWED_ORIGINS.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtest_router)
app.include_router(fund_router)
app.include_router(admin_router)
app.include_router(research_router)
app.include_router(blog_router)
app.include_router(monitoring_router)
app.include_router(knowledge_router)

_PUBLIC_PATHS = {"/health", "/ws", "/ws/agents", "/docs", "/openapi.json", "/redoc"}

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    if settings.ENV == "dev" or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if key != settings.API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)

@app.on_event("startup")
async def startup_event():
    from app.storage.db import init_db
    from app.monitoring import monitor
    from app.fund.task_bus import task_bus
    from app.websocket.agent_events import agent_event_stream
    from pathlib import Path
    import os
    
    global _current_dev_session
    
    # Set up event loop for WebSocket event broadcasting
    try:
        loop = asyncio.get_running_loop()
        agent_event_stream.set_event_loop(loop)
        logger.info("Agent event stream event loop configured")
    except Exception as e:
        logger.warning(f"Failed to set event loop for agent events: {e}")
    
    # Start devlog session (per DevViktor.md requirement)
    try:
        dev_logger = get_dev_logger(repo_root=str(Path(__file__).parent.parent.parent))
        _current_dev_session = dev_logger.start_session(
            scope="Backend server runtime - monitoring, API integration, and fund system operations",
            files=[
                "backend/app/main.py",
                "backend/app/monitoring.py",
                "backend/app/monitoring_routes.py",
                "backend/app/devlog.py",
                "backend/app/knowledge_routes.py",
                "backend/app/admin_research_routes.py",
            ],
            notes="Automated session start on server boot",
        )
    except Exception as e:
        logger.warning(f"Could not start devlog session: {e}")
    
    # Log startup sequence
    monitor.log_startup_sequence()
    
    # Initialize database
    try:
        init_db()
        monitor.log_component_status("Database", "OK", "trading_bot.db initialized")
    except Exception as e:
        monitor.log_component_status("Database", "ERROR", str(e))
        raise

    # Restore persisted task history so lineage survives backend restarts.
    try:
        restored = task_bus.restore_from_storage()
        monitor.log_component_status(
            "Task Bus",
            "OK",
            f"restored={restored.get('restored')} events={restored.get('event_count')} tasks={restored.get('task_count')}",
        )
    except Exception as e:
        monitor.log_component_status("Task Bus", "WARN", str(e))
    
    # Setup event capture
    try:
        def _capture_openclaw_command_event(event: dict[str, Any]) -> None:
            captured = knowledge_graph.capture("openclaw_command", event)
            realtime_stream.publish(source="openclaw_command", event=captured)

        openclaw_command_adapter.set_event_sink(_capture_openclaw_command_event)
        monitor.log_component_status("OpenClaw Adapter", "OK", "Event sink configured")
    except Exception as e:
        monitor.log_component_status("OpenClaw Adapter", "WARN", str(e))
    
    # Restore broker state
    try:
        broker.restore_from_db()
        monitor.log_component_status("Broker State", "OK", f"Restored: cash=${float(broker.get_cash()):,.2f}")
    except Exception as e:
        monitor.log_component_status("Broker State", "WARN", str(e))
    
    # Start market data stream
    try:
        asyncio.create_task(stream_loop())
        monitor.log_component_status("Market Data Stream", "OK", "WebSocket loop started")
    except Exception as e:
        monitor.log_component_status("Market Data Stream", "WARN", str(e))
    
    # Auto trading
    if settings.AUTO_TRADING_ENABLED:
        try:
            from app.strategies.auto_trader import auto_trading_loop
            asyncio.create_task(auto_trading_loop())
            monitor.log_component_status("Auto Trader", "OK", "Legacy auto-trader loop enabled")
        except Exception as e:
            monitor.log_component_status("Auto Trader", "ERROR", str(e))
    else:
        monitor.log_component_status("Auto Trader", "OK", "Disabled (manual trading mode)")
    
    # Agent runtime
    if settings.AGENT_RUNTIME_ENABLED:
        try:
            await fund_agent_runtime.start()
            monitor.log_component_status("Agent Runtime", "OK", "Fund agent runtime started")
        except Exception as e:
            monitor.log_component_status("Agent Runtime", "ERROR", str(e))
    else:
        monitor.log_component_status("Agent Runtime", "OK", "Disabled")
    
    # ML Models
    try:
        from app.ml.alpha_model import ensure_model, model_status
        ensure_model()
        alpha_status = model_status()
        if alpha_status.get("ready"):
            monitor.log_component_status(
                "Alpha Model",
                "OK",
                f"ready features={alpha_status.get('features', 0)}",
            )
        elif alpha_status.get("training"):
            monitor.log_component_status("Alpha Model", "WARN", "training_in_progress")
        else:
            monitor.log_component_status(
                "Alpha Model",
                "WARN",
                "not_ready (optional deps/model may be unavailable)",
            )
    except Exception as e:
        monitor.log_component_status("Alpha Model", "WARN", str(e))
    
    # Sentiment Model
    try:
        from app.utils.sentiment import _ensure_finbert, sentiment_model_status
        _ensure_finbert()
        sent_status = sentiment_model_status()
        if sent_status.get("finbert_available"):
            monitor.log_component_status("Sentiment Model", "OK", "finbert_ready")
        elif sent_status.get("finbert_loading"):
            monitor.log_component_status("Sentiment Model", "WARN", "finbert_loading_using_vader")
        else:
            monitor.log_component_status("Sentiment Model", "WARN", "using_vader_fallback")
    except Exception as e:
        monitor.log_component_status("Sentiment Model", "WARN", str(e))
    
    # Print fund statistics
    await asyncio.sleep(1)  # Give components time to initialize
    monitor.log_fund_stats()
    logger.info("ALFRED READY - All systems operational")

@app.on_event("shutdown")
async def shutdown_event():
    global _current_dev_session
    
    # Log session end (per DevViktor.md requirement)
    if _current_dev_session:
        try:
            from app.devlog import get_dev_logger
            dev_logger = get_dev_logger()
            dev_logger.end_session(
                entry=_current_dev_session,
                validation="completed",
                notes="Server shutdown - session ended normally",
            )
            logger.info(f"Dev session logged: {_current_dev_session.entry_id}")
        except Exception as e:
            logger.warning(f"Could not end devlog session: {e}")
    
    if fund_agent_runtime.is_started():
        await fund_agent_runtime.stop()


@app.get("/health")
async def health():
    from app.ml.alpha_model import model_status
    from app.utils.sentiment import sentiment_model_name, sentiment_model_status
    return {
        "status": "ok", "version": "5.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "watchlist": WATCHLIST,
        "connected_clients": len(manager.active),
        "ml_model": model_status(),
        "sentiment_model": sentiment_model_name(),
        "sentiment_model_status": sentiment_model_status(),
        "risk": risk.status(),
        "fund": {
            "active_tasks": len(firm_orchestrator.list_active_tasks()),
            "pending_decisions": len(firm_orchestrator.list_pending_decisions()),
            "knowledge_events": firm_orchestrator.knowledge_stats().get("event_count", 0),
            "agent_runtime_started": fund_agent_runtime.is_started(),
        },
    }


@app.get("/debug/websocket-stream")
async def debug_websocket_stream():
    """Debug endpoint to check WebSocket event stream status."""
    from app.websocket.agent_events import agent_event_stream
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "active_connections": len(agent_event_stream.active),
        "event_buffer_size": len(agent_event_stream._event_buffer),
        "recent_events": agent_event_stream.get_recent_events(limit=5),
        "agent_status_cache_count": len(agent_event_stream._agent_status_cache),
        "event_loop_configured": agent_event_stream._event_loop is not None,
        "agent_status_sample": list(agent_event_stream._agent_status_cache.items())[:3],
    }


@app.post("/signals/generate")
async def generate_signal(req: SignalRequest) -> Dict[str, Any]:
    if data_integrity_guard.halted():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "system_halted",
                "reason": data_integrity_guard.halt_reason() or "strict_real_data_halt",
                "message": (
                    "Strict real-data mode halted the runtime after provider fallback/failure. "
                    "Signal generation is blocked."
                ),
            },
        )
    result = hybrid_signal(req.symbol)
    if data_integrity_guard.halted():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "system_halted",
                "reason": data_integrity_guard.halt_reason() or "strict_real_data_halt",
                "message": (
                    "Strict real-data mode halted the runtime after provider fallback/failure. "
                    "Signal generation result discarded."
                ),
            },
        )
    return result

@app.get("/paper/positions")
async def get_positions():
    return broker.list_positions(lambda s: FEED.price(s))

@app.get("/paper/orders")
async def get_orders():
    return broker.list_orders()

@app.post("/paper/order")
async def place_order(order: OrderIn, request: Request):
    from app.fund.audit_log import audit_log
    from app.fund.contracts import DecisionRecord, Sleeve, make_immutable_id
    from app.fund.decision_ledger import decision_ledger

    if data_integrity_guard.halted():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "system_halted",
                "reason": data_integrity_guard.halt_reason() or "strict_real_data_halt",
                "message": (
                    "Strict real-data mode halted the runtime after provider fallback/failure. "
                    "Order placement is blocked."
                ),
            },
        )

    price = FEED.price(order.symbol)
    if data_integrity_guard.halted():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "system_halted",
                "reason": data_integrity_guard.halt_reason() or "strict_real_data_halt",
                "message": (
                    "Strict real-data mode halted the runtime after provider fallback/failure. "
                    "Order placement aborted."
                ),
            },
        )
    run_id = request.headers.get("X-Run-Id") or make_immutable_id(
        "run", "manual", order.symbol, order.side, order.quantity, datetime.utcnow().isoformat()
    )
    agent_id = request.headers.get("X-Agent-Id") or "manual_trader"
    thesis_id = make_immutable_id("thesis", run_id, "manual")
    decision_id = request.headers.get("X-Decision-Id") or make_immutable_id(
        "decision", run_id, thesis_id, order.symbol, order.side, order.quantity, price
    )
    risk_id = make_immutable_id("risk", decision_id, "legacy_risk_engine")
    intent_id = make_immutable_id("intent", decision_id, order.symbol, order.side, order.quantity)
    decision_ledger.add_decision(
        DecisionRecord(
            decision_id=decision_id,
            run_id=run_id,
            agent_id=agent_id,
            sleeve=Sleeve.TACTICAL,
            thesis_id=thesis_id,
            risk_id=risk_id,
            intent_id=intent_id,
            status="proposed",
        )
    )
    positions = broker.list_positions(lambda s: FEED.price(s))
    approved, reason = risk.pre_trade_check(order.symbol, order.side, order.quantity, price, positions)
    if not approved:
        audit_log.record_pre_trade_decision(
            approved=False,
            run_id=run_id,
            decision_id=decision_id,
            agent_id=agent_id,
            blocked_reasons=[reason],
            policy_gate_id="legacy_risk_engine",
            policy_version="legacy_risk_engine",
            metadata={
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "intent_id": intent_id,
                "risk_id": risk_id,
            },
        )
        decision_ledger.update_status(decision_id, "blocked", {"reason": reason})
        decision_ledger.add_event(
            event_type="paper.order.blocked",
            decision_id=decision_id,
            order_id=None,
            payload={"reason": reason, "symbol": order.symbol, "side": order.side},
        )
        return {
            "error": reason,
            "approved": False,
            "run_id": run_id,
            "decision_id": decision_id,
            "risk_id": risk_id,
            "intent_id": intent_id,
        }
    audit_log.record_pre_trade_decision(
        approved=True,
        run_id=run_id,
        decision_id=decision_id,
        agent_id=agent_id,
        policy_gate_id="legacy_risk_engine",
        policy_version="legacy_risk_engine",
        metadata={
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "intent_id": intent_id,
            "risk_id": risk_id,
        },
    )
    created = broker.submit_order(order.symbol, order.side, order.quantity, price)
    decision_ledger.update_status(decision_id, "executed", {"order_id": created.id})
    decision_ledger.add_event(
        event_type="paper.order.executed",
        decision_id=decision_id,
        order_id=created.id,
        payload={
            "symbol": created.symbol,
            "side": created.side,
            "quantity": created.qty,
            "price": created.avg_price,
        },
    )
    audit_log.record(
        "paper.order.executed",
        {
            "run_id": run_id,
            "decision_id": decision_id,
            "risk_id": risk_id,
            "intent_id": intent_id,
            "order_id": created.id,
            "symbol": created.symbol,
            "side": created.side,
            "quantity": created.qty,
            "price": created.avg_price,
            "agent_id": agent_id,
        },
    )
    if order.side == "buy":
        from app.strategies.auto_trader import _current_atr
        atr_val = _current_atr(order.symbol)
        if atr_val > 0:
            risk.register_entry(order.symbol, price, atr_val, "long")
    positions = broker.list_positions(lambda s: FEED.price(s))
    await manager.broadcast({"type": "positions_update", "data": positions, "ts": datetime.utcnow().isoformat()})
    return {
        "id": created.id, "symbol": created.symbol, "side": created.side,
        "quantity": created.qty, "price": created.avg_price,
        "timestamp": created.created_at.isoformat(), "status": created.status, "approved": True,
        "run_id": run_id, "decision_id": decision_id, "risk_id": risk_id, "intent_id": intent_id,
    }

@app.get("/news/{symbol}")
async def get_news(symbol: str):
    items = latest_news(symbol)
    return [{
        "symbol": it.get("symbol", symbol.upper()), "headline": it.get("headline", ""),
        "source": it.get("source", "Finnhub"), "url": it.get("url", ""),
        "published_at": it.get("published_at") or datetime.utcnow().isoformat(),
    } for it in items]

@app.get("/analytics/summary")
async def analytics_summary() -> Dict[str, Any]:
    return build_metrics_from_broker(broker)

@app.get("/risk/status")
async def risk_status():
    positions = broker.list_positions(lambda s: FEED.price(s))
    analytics = build_metrics_from_broker(broker)
    risk.update_equity(positions, analytics.get("realized_pnl", 0.0))
    return risk.status()

@app.get("/market/prices")
async def market_prices():
    return {sym: FEED.price(sym) for sym in WATCHLIST}

@app.get("/ml/status")
async def ml_status():
    from app.ml.alpha_model import model_status
    from app.utils.sentiment import sentiment_model_name
    return {"lgbm": model_status(), "sentiment": sentiment_model_name()}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.websocket("/ws/agents")
async def websocket_agent_events(ws: WebSocket):
    """WebSocket endpoint for real-time agent orchestration events.
    
    Clients connecting to this endpoint receive:
    - Initial agent status snapshot
    - Real-time updates for agent state changes
    - Task events (started, completed, failed)
    - Orchestration decisions
    - Trade executions
    """
    await agent_event_stream.connect(ws)
    try:
        while True:
            # Just keep connection open; events are broadcast from task bus
            await ws.receive_text()
    except WebSocketDisconnect:
        await agent_event_stream.disconnect(ws)
        
