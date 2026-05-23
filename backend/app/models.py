from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


class SignalRequest(BaseModel):
    symbol: str = Field(..., description="Ticker, e.g., AAPL")
    lookback: int = Field(150, ge=20, le=2000, description="Candles to analyze")
    profile: Optional[Literal["accuracy_max", "balanced", "latency_low", "risk_off"]] = Field(
        None,
        description="Core-engine model profile",
    )


class OrderIn(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)   # BUG FIX: was missing, frontend sent qty


class Order(BaseModel):
    id: str                              # BUG FIX: was int - PaperBroker generates UUID str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    timestamp: datetime
    status: Literal["filled", "pending", "cancelled"]


class Position(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    market_price: float
    market_value: float
    unrealized_pnl: float


class NewsItem(BaseModel):
    symbol: str
    headline: str
    source: str
    url: str
    published_at: datetime

