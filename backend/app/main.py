from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.context import broker
from app.models import SignalRequest, OrderIn
from app.strategies.hybrid import hybrid_signal
from app.data.news import latest_news
from app.analytics import build_metrics_from_broker
from app.websocket.stream import manager, stream_loop, WATCHLIST
from app.data.market_data import FEED
from app.risk.engine import risk
from app.backtest.router import router as backtest_router
from app.config import get_settings

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

_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
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

_PUBLIC_PATHS = {"/health", "/ws", "/docs", "/openapi.json", "/redoc"}

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
    init_db()
    broker.restore_from_db()
    asyncio.create_task(stream_loop())
    from app.strategies.auto_trader import auto_trading_loop
    asyncio.create_task(auto_trading_loop())
    from app.ml.alpha_model import ensure_model
    ensure_model()
    from app.utils.sentiment import _ensure_finbert
    _ensure_finbert()
    logger.info("ALFRED started — version 5.1.0")

@app.get("/health")
async def health():
    from app.ml.alpha_model import model_status
    from app.utils.sentiment import sentiment_model_name
    return {
        "status": "ok", "version": "5.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "watchlist": WATCHLIST,
        "connected_clients": len(manager.active),
        "ml_model": model_status(),
        "sentiment_model": sentiment_model_name(),
        "risk": risk.status(),
    }

@app.post("/signals/generate")
async def generate_signal(req: SignalRequest) -> Dict[str, Any]:
    return hybrid_signal(req.symbol)

@app.get("/paper/positions")
async def get_positions():
    return broker.list_positions(lambda s: FEED.price(s))

@app.get("/paper/orders")
async def get_orders():
    return broker.list_orders()

@app.post("/paper/order")
async def place_order(order: OrderIn):
    price = FEED.price(order.symbol)
    positions = broker.list_positions(lambda s: FEED.price(s))
    approved, reason = risk.pre_trade_check(order.symbol, order.side, order.quantity, price, positions)
    if not approved:
        return {"error": reason, "approved": False}
    created = broker.submit_order(order.symbol, order.side, order.quantity, price)
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
        