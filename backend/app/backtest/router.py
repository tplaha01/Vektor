from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.backtest.engine import run_backtest, result_to_dict, BacktestConfig
from app.config import get_settings

router = APIRouter(prefix="/backtest", tags=["backtest"])

S = get_settings()


class BacktestRequest(BaseModel):
    symbol: str
    period: str = "1y"
    initial_equity: float = 100_000.0
    buy_threshold: float = S.BUY_THRESHOLD
    sell_threshold: float = S.SELL_THRESHOLD
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    benchmark: str = "SPY"


@router.post("/run")
async def run(req: BacktestRequest):
    try:
        cfg = BacktestConfig(
            initial_equity=req.initial_equity,
            buy_threshold=req.buy_threshold,
            sell_threshold=req.sell_threshold,
            commission_pct=req.commission_pct,
            slippage_pct=req.slippage_pct,
        )
        result = run_backtest(req.symbol, period=req.period, config=cfg, benchmark=req.benchmark)
        return result_to_dict(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest error: {e}")


@router.get("/run")
async def run_get(
    symbol: str = Query(...),
    period: str = Query("1y"),
    benchmark: str = Query("SPY"),
):
    try:
        result = run_backtest(symbol, period=period, benchmark=benchmark)
        return result_to_dict(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest error: {e}")