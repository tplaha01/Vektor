from __future__ import annotations
from datetime import datetime
import pandas as pd

from ta.volatility import AverageTrueRange

from app.config import get_settings
from app.data.market_data import FEED
from app.data.fundamentals import get_fundamentals
from app.data.news import latest_news
from app.indicators.technical import technical_score
from app.utils.sentiment import sentiment_score, sentiment_model_name
from app.utils.common import clamp


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder ATR via `ta` library (consistent with other components).
    """
    ind = AverageTrueRange(
        high=df["high"].astype(float),
        low=df["low"].astype(float),
        close=df["close"].astype(float),
        window=period,
        fillna=False,
    )
    return ind.average_true_range()


def hybrid_signal(symbol: str) -> dict:
    settings = get_settings()

    BUY_THR  = settings.BUY_THRESHOLD
    SELL_THR = settings.SELL_THRESHOLD
    ATR_N    = settings.ATR_PERIOD
    VOL_CAP  = settings.VOL_THRESHOLD

    hist = FEED.history(symbol, bars=200)
    empty = hist is None or len(hist) < max(60, ATR_N + 2)
    if not empty:
        empty = hist[["close", "high", "low"]].isna().any().any()

    if empty:
        return _empty_signal(symbol, settings)

    # ── Technical score ──────────────────────────────────────────────────
    t_score = clamp(technical_score(hist))

    # ── Fundamental score ────────────────────────────────────────────────
    f = get_fundamentals(symbol)
    f_score = 0.0
    f_score += min(f.get("revenue_growth", 0.0), 0.3) * (1 / 0.3) * 0.35
    f_score += min(f.get("gross_margin",   0.0), 0.7) * (1 / 0.7) * 0.35
    f_score += min(f.get("oper_margin",    0.0), 0.5) * (1 / 0.5) * 0.30
    f_score -= min(f.get("debt_to_equity", 1.0) / 3.0, 1.0) * 0.25
    f_score -= min(f.get("pe", 20.0) / 60.0, 1.0) * 0.25
    f_score = clamp(f_score)

    # ── Sentiment score ──────────────────────────────────────────────────
    news = latest_news(symbol)
    texts = [n["headline"] for n in news if n.get("headline")]
    s_score = clamp(sentiment_score(texts))

    # ── ML alpha score ───────────────────────────────────────────────────
    ml_score = 0.0
    ml_ready = False
    try:
        from app.ml.alpha_model import predict, model_status
        st = model_status()
        if st.get("ready"):
            # alpha_model accepts ts or date; FEED likely provides ts already
            ml_score = clamp(predict(hist))
            ml_ready = True
    except Exception as e:
        print(f"⚠️ ML alpha skipped: {e}")

    # ── Weighted ensemble ────────────────────────────────────────────────
    wT = settings.TECH_WEIGHT
    wF = settings.FUND_WEIGHT
    wS = settings.SENT_WEIGHT
    wM = settings.ML_WEIGHT

    if ml_ready:
        total_w = wT + wF + wS + wM
        score = clamp((wT * t_score + wF * f_score + wS * s_score + wM * ml_score) / (total_w + 1e-9))
    else:
        total_w = wT + wF + wS
        score = clamp((wT * t_score + wF * f_score + wS * s_score) / (total_w + 1e-9))

    # ── Volatility filter ────────────────────────────────────────────────
    vol_ratio = None
    action = "hold"
    try:
        atr_series = atr(hist, ATR_N)
        atr_val = float(atr_series.iloc[-1])
        px = float(hist["close"].iloc[-1])
        vol_ratio = atr_val / px if px != 0.0 else 0.0

        if vol_ratio > VOL_CAP:
            action = "hold"
        else:
            action = "buy" if score > BUY_THR else ("sell" if score < SELL_THR else "hold")

    except Exception as e:
        print(f"⚠️ ATR calc failed for {symbol}: {e}")

    return {
        "symbol": symbol.upper(),
        "timestamp": datetime.utcnow().isoformat(),
        "subscores": {
            "technical": round(t_score, 4),
            "fundamental": round(f_score, 4),
            "sentiment": round(s_score, 4),
            "ml_alpha": round(ml_score, 4),
        },
        "weights": {
            "technical": wT,
            "fundamental": wF,
            "sentiment": wS,
            "ml_alpha": wM,
        },
        "score": round(score, 4),
        "action": action,
        "volatility": round(vol_ratio, 4) if vol_ratio is not None else None,
        "ml_ready": ml_ready,
        "sentiment_model": sentiment_model_name(),
    }


def _empty_signal(symbol: str, settings) -> dict:
    return {
        "symbol": symbol.upper(),
        "timestamp": datetime.utcnow().isoformat(),
        "subscores": {"technical": 0.0, "fundamental": 0.0, "sentiment": 0.0, "ml_alpha": 0.0},
        "weights": {
            "technical": settings.TECH_WEIGHT,
            "fundamental": settings.FUND_WEIGHT,
            "sentiment": settings.SENT_WEIGHT,
            "ml_alpha": settings.ML_WEIGHT,
        },
        "score": 0.0,
        "action": "hold",
        "volatility": None,
        "ml_ready": False,
        "sentiment_model": sentiment_model_name(),
    }