from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.core_engine.contracts import DomainModelOutput, EngineInputSnapshot
from app.quant.regime import infer_market_regime
from app.quant.statistics import adx_triplet, atr_pct, bollinger_position, macd_hist, rsi, stoch, volume_ratio
from app.utils.common import clamp


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        pass
    return default


def run_technical_pack(snapshot: EngineInputSnapshot) -> DomainModelOutput:
    hist = snapshot.history
    if len(hist) < 80:
        return DomainModelOutput(
            name="technical",
            alpha=0.0,
            uncertainty=1.0,
            diagnostics={"reason": "insufficient_market_history", "bars": int(len(hist))},
        )

    c = hist["close"].astype(float)
    h = hist["high"].astype(float)
    l = hist["low"].astype(float)
    v = hist["volume"].astype(float).fillna(0.0)

    snap = infer_market_regime(hist)
    adx, adx_pos, adx_neg = adx_triplet(c, h, l)
    atrp = atr_pct(c, h, l)
    bb_pct, bb_width = bollinger_position(c)
    rsi_val = rsi(c)
    stoch_val = stoch(h, l, c)
    macd_val, macd_accel = macd_hist(c)
    volr = volume_ratio(v)

    breakout_up = float(c.iloc[-1] > h.tail(20).max())
    breakout_down = float(c.iloc[-1] < l.tail(20).min())
    trap_down = float(l.iloc[-1] < l.tail(10).min() and c.iloc[-1] > c.iloc[-2])
    trap_up = float(h.iloc[-1] > h.tail(10).max() and c.iloc[-1] < c.iloc[-2])
    liquidity_trap = trap_down - trap_up

    alpha = clamp(
        0.30 * _safe_float(snap.edge)
        + 0.18 * clamp((adx_pos - adx_neg) / 30.0)
        + 0.14 * clamp((rsi_val - 50.0) / 25.0)
        + 0.12 * clamp(macd_val * 8.0)
        + 0.10 * clamp((stoch_val - 50.0) / 30.0)
        + 0.10 * clamp((bb_pct - 0.5) * 2.0)
        + 0.06 * clamp(liquidity_trap)
    )

    stability = float(np.clip(1.0 - (abs(atrp - 0.025) / 0.05), 0.0, 1.0))
    uncertainty = float(np.clip(0.85 - 0.55 * stability - 0.25 * min(1.0, abs(alpha)), 0.05, 1.0))

    return DomainModelOutput(
        name="technical",
        alpha=alpha,
        uncertainty=uncertainty,
        diagnostics={
            "regime": snap.regime,
            "regime_edge": _safe_float(snap.edge),
            "adx": adx,
            "atr_pct": atrp,
            "rsi": rsi_val,
            "stoch": stoch_val,
            "macd_hist": macd_val,
            "macd_accel": macd_accel,
            "bb_pct": bb_pct,
            "bb_width": bb_width,
            "volume_ratio": volr,
            "breakout_up": breakout_up,
            "breakout_down": breakout_down,
            "liquidity_trap": liquidity_trap,
        },
    )
