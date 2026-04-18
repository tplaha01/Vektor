from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

try:
    from ta.volatility import AverageTrueRange as _TaAverageTrueRange
except Exception:
    _TaAverageTrueRange = None

from app.config import get_settings
from app.data.market_data import FEED
from app.data.fundamentals import get_fundamentals
from app.data.news import latest_news
from app.indicators.technical import technical_score
from app.utils.sentiment import sentiment_score, sentiment_model_name
from app.utils.common import clamp

_log = logging.getLogger("alfred.strategy.hybrid")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    ATR series with graceful fallback when `ta` is unavailable.
    """
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    if _TaAverageTrueRange is not None:
        ind = _TaAverageTrueRange(high=high, low=low, close=close, window=period, fillna=False)
        return ind.average_true_range()

    # Wilder ATR fallback (RMA of true range).
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / max(int(period), 1), adjust=False, min_periods=period).mean()


def hybrid_signal(symbol: str) -> dict:
    settings = get_settings()

    buy_thr = settings.BUY_THRESHOLD
    sell_thr = settings.SELL_THRESHOLD
    atr_n = settings.ATR_PERIOD
    vol_cap = settings.VOL_THRESHOLD

    hist = FEED.history(symbol, bars=200)
    empty = hist is None or len(hist) < max(60, atr_n + 2)
    if not empty:
        empty = hist[["close", "high", "low"]].isna().any().any()

    if empty:
        return _empty_signal(symbol, settings)

    # Technical score
    t_score = clamp(technical_score(hist))

    # Fundamental score
    f = get_fundamentals(symbol)
    f_score = 0.0
    f_score += min(f.get("revenue_growth", 0.0), 0.3) * (1 / 0.3) * 0.35
    f_score += min(f.get("gross_margin", 0.0), 0.7) * (1 / 0.7) * 0.35
    f_score += min(f.get("oper_margin", 0.0), 0.5) * (1 / 0.5) * 0.30
    f_score -= min(f.get("debt_to_equity", 1.0) / 3.0, 1.0) * 0.25
    f_score -= min(f.get("pe", 20.0) / 60.0, 1.0) * 0.25
    f_score = clamp(f_score)

    # Sentiment score
    news = latest_news(symbol)
    texts = [n["headline"] for n in news if n.get("headline")]
    s_score = clamp(sentiment_score(texts))

    # ML alpha score
    ml_score = 0.0
    ml_ready = False
    try:
        from app.ml.alpha_model import model_status, predict

        st = model_status()
        if st.get("ready"):
            ml_score = clamp(predict(hist))
            ml_ready = True
    except Exception as exc:
        _log.debug("ml_alpha_unavailable: %s", exc)

    # Weighted ensemble
    w_t = settings.TECH_WEIGHT
    w_f = settings.FUND_WEIGHT
    w_s = settings.SENT_WEIGHT
    w_m = settings.ML_WEIGHT

    if ml_ready:
        total_w = w_t + w_f + w_s + w_m
        score = clamp((w_t * t_score + w_f * f_score + w_s * s_score + w_m * ml_score) / (total_w + 1e-9))
    else:
        total_w = w_t + w_f + w_s
        score = clamp((w_t * t_score + w_f * f_score + w_s * s_score) / (total_w + 1e-9))

    # Volatility filter
    vol_ratio = None
    action = "hold"
    try:
        atr_series = atr(hist, atr_n)
        atr_val = float(atr_series.iloc[-1])
        px = float(hist["close"].iloc[-1])
        vol_ratio = atr_val / px if px != 0.0 else 0.0

        if vol_ratio > vol_cap:
            action = "hold"
        else:
            action = "buy" if score > buy_thr else ("sell" if score < sell_thr else "hold")

    except Exception as exc:
        _log.warning("atr_calc_failed symbol=%s error=%s", symbol, exc)

    return {
        "symbol": symbol.upper(),
        "timestamp": _utc_iso(),
        "subscores": {
            "technical": round(t_score, 4),
            "fundamental": round(f_score, 4),
            "sentiment": round(s_score, 4),
            "ml_alpha": round(ml_score, 4),
        },
        "weights": {
            "technical": w_t,
            "fundamental": w_f,
            "sentiment": w_s,
            "ml_alpha": w_m,
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
        "timestamp": _utc_iso(),
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
