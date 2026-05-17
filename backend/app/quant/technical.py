from __future__ import annotations

import numpy as np
import pandas as pd

from app.quant.statistics import AverageTrueRange


def detect_regime(c, h, l, v, adx_val, adx_pos, adx_neg):
    atr_val = AverageTrueRange(h, l, c, window=14, fillna=True).average_true_range().iloc[-1] if AverageTrueRange is not None else 0.0
    atr_pct = float(atr_val / (c.iloc[-1] + 1e-9))
    if atr_pct > 0.045:
        return "HIGH_VOL", atr_pct
    vol_mean = v.rolling(20).mean().iloc[-1]
    vol_ratio = float(v.iloc[-1] / (vol_mean + 1e-9))
    high_20 = h.rolling(20).max().iloc[-2]
    low_20 = l.rolling(20).min().iloc[-2]
    if vol_ratio > 2.0:
        if c.iloc[-1] > high_20:
            return "BREAKOUT_UP", atr_pct
        if c.iloc[-1] < low_20:
            return "BREAKOUT_DOWN", atr_pct
    if adx_val > 25:
        return ("TREND_UP" if adx_pos > adx_neg else "TREND_DOWN"), atr_pct
    return "RANGE", atr_pct


def technical_score(df: pd.DataFrame, debug: bool = False):
    from app.quant.regime import infer_market_regime

    snapshot = infer_market_regime(df)
    score = float(np.clip(snapshot.edge, -1.0, 1.0))
    if debug:
        return {
            "regime": snapshot.regime,
            "adx": None if snapshot.adx is None else round(float(snapshot.adx), 2),
            "atr_pct": None if snapshot.atr_pct is None else round(float(snapshot.atr_pct) * 100, 3),
            "score": round(score, 4),
            "direction": snapshot.direction,
            "confidence": round(float(snapshot.confidence), 4),
            "edge": round(float(snapshot.edge), 4),
        }
    return score
