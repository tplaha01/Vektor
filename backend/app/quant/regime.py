from __future__ import annotations

import numpy as np
import pandas as pd

from app.quant.common import (
    _clip,
    _price_group,
    _safe_float,
    _series_close_high_low_volume,
    _trend_sign,
    clip,
    close_high_low_volume,
    price_group,
    safe_float,
    trend_sign,
)
from app.quant.risk import infer_portfolio_risk_regime
from app.quant.statistics import (
    AverageTrueRange,
    _adx_triplet,
    _atr_pct,
    _bollinger_position,
    _fallback_adx_triplet,
    _fallback_bollinger_position,
    _fallback_macd_hist,
    _fallback_rsi,
    _fallback_stoch,
    _liquidity_score,
    _macd_hist,
    _rsi,
    _stoch,
    _volume_ratio,
    adx_triplet,
    atr_pct,
    bollinger_position,
    liquidity_score,
    macd_hist,
    realised_volatility,
    rsi,
    stoch,
    volume_ratio,
)
from app.quant.types import MarketRegimeSnapshot, PortfolioRegimeSnapshot


def infer_market_regime(df: pd.DataFrame) -> MarketRegimeSnapshot:
    if df is None or len(df) < 60:
        return MarketRegimeSnapshot(
            regime="RANGE",
            direction="neutral",
            confidence=0.0,
            edge=0.0,
            trend_score=0.0,
            breakout_score=0.0,
            mean_reversion_score=0.0,
            volatility_score=0.0,
            liquidity_score=0.0,
            notes=("insufficient_history",),
            metrics={},
        )

    close, high, low, volume = close_high_low_volume(df)
    adx, adx_pos, adx_neg = adx_triplet(close, high, low)
    atr_percent = atr_pct(close, high, low)
    rsi_value = rsi(close)
    stoch_value = stoch(high, low, close)
    macd_value, macd_accel = macd_hist(close)
    bb_pct, bb_width = bollinger_position(close)
    vol_ratio = volume_ratio(volume)
    liq_score = liquidity_score(close, volume)

    sma20 = safe_float(close.rolling(20).mean().iloc[-1])
    sma50 = safe_float(close.rolling(50).mean().iloc[-1])
    ema12 = safe_float(close.ewm(span=12, adjust=False).mean().iloc[-1])
    ema26 = safe_float(close.ewm(span=26, adjust=False).mean().iloc[-1])
    close_px = safe_float(close.iloc[-1])
    prev_5 = safe_float(close.iloc[-6] if len(close) > 5 else close.iloc[0], close_px)
    prev_20 = safe_float(close.iloc[-21] if len(close) > 20 else close.iloc[0], close_px)
    momentum_5 = (close_px - prev_5) / (prev_5 + 1e-9)
    momentum_20 = (close_px - prev_20) / (prev_20 + 1e-9)
    roc3 = (close_px - safe_float(close.iloc[-4] if len(close) > 3 else close.iloc[0], close_px)) / (close_px + 1e-9)
    zscore_20 = safe_float((close_px - close.rolling(20).mean().iloc[-1]) / (close.rolling(20).std().iloc[-1] + 1e-9))

    trend_score = clip(
        (
            0.22 * trend_sign(close_px - sma20)
            + 0.16 * trend_sign(close_px - sma50)
            + 0.16 * trend_sign(ema12 - ema26)
            + 0.14 * trend_sign(adx_pos - adx_neg) * min(adx / 40.0, 1.0)
            + 0.16 * clip(momentum_5 * 12.0)
            + 0.16 * clip(momentum_20 * 8.0)
        )
    )

    breakout_up = max(0.0, (close_px / (safe_float(high.tail(20).max()) + 1e-9)) - 1.0)
    breakout_down = max(0.0, (safe_float(low.tail(20).min()) / (close_px + 1e-9)) - 1.0)
    breakout_direction = 1.0 if breakout_up >= breakout_down else -1.0 if breakout_down > breakout_up else 0.0
    breakout_score = clip(
        (
            0.38 * clip((vol_ratio - 1.0) / 1.5, 0.0, 1.0)
            + 0.34 * clip(max(breakout_up, breakout_down) * 22.0, 0.0, 1.0)
            + 0.16 * clip(abs(roc3) * 20.0, 0.0, 1.0)
            + 0.12 * trend_sign(breakout_up - breakout_down)
        )
        * breakout_direction
    )

    bullish_conditions = sum([bb_pct < 0.10, rsi_value < 32.0, stoch_value < 24.0, zscore_20 < -1.75])
    bearish_conditions = sum([bb_pct > 0.90, rsi_value > 68.0, stoch_value > 76.0, zscore_20 > 1.75])
    if bullish_conditions >= 2:
        mean_reversion_score = float(min(1.0, 0.5 + 0.18 * (bullish_conditions - 2)))
    elif bearish_conditions >= 2:
        mean_reversion_score = float(max(-1.0, -(0.5 + 0.18 * (bearish_conditions - 2))))
    else:
        mean_reversion_score = 0.0

    volatility_score = float(np.clip(1.0 - abs(atr_percent - 0.025) / 0.04, 0.0, 1.0))
    direction_score = (
        0.44 * trend_score
        + 0.24 * breakout_score
        + 0.20 * mean_reversion_score
        + 0.07 * clip(momentum_5 * 10.0)
        + 0.05 * clip((bb_width - 0.04) / 0.08)
    )
    confidence = float(
        np.clip(
            (
                0.34 * abs(trend_score)
                + 0.24 * abs(breakout_score)
                + 0.18 * abs(mean_reversion_score)
                + 0.14 * volatility_score
                + 0.10 * liq_score
            ),
            0.0,
            1.0,
        )
    )

    notes: list[str] = []
    if adx >= 25.0:
        notes.append("adx_trend")
    if vol_ratio >= 1.5:
        notes.append("volume_expansion")
    if volatility_score >= 0.75:
        notes.append("volatility_orderly")
    if bullish_conditions >= 2 or bearish_conditions >= 2:
        notes.append("mean_reversion_extreme")
    if abs(direction_score) < 0.12:
        notes.append("low_directional_edge")

    if volatility_score >= 0.80 and abs(direction_score) < 0.22:
        regime = "HIGH_VOL"
    elif abs(breakout_score) >= 0.50 and vol_ratio >= 1.35:
        regime = "BREAKOUT_UP" if breakout_score > 0 else "BREAKOUT_DOWN"
    elif abs(trend_score) >= 0.42 and adx >= 20.0:
        regime = "TREND_UP" if trend_score > 0 else "TREND_DOWN"
    elif abs(mean_reversion_score) >= 0.40:
        regime = "MEAN_REVERT_UP" if mean_reversion_score > 0 else "MEAN_REVERT_DOWN"
    else:
        regime = "RANGE"

    if regime in {"TREND_UP", "BREAKOUT_UP", "MEAN_REVERT_UP"}:
        direction = "long_bias"
    elif regime in {"TREND_DOWN", "BREAKOUT_DOWN", "MEAN_REVERT_DOWN"}:
        direction = "short_bias"
    elif direction_score > 0.15:
        direction = "long_bias"
    elif direction_score < -0.15:
        direction = "short_bias"
    else:
        direction = "neutral"

    if regime == "HIGH_VOL" and direction == "neutral" and abs(mean_reversion_score) >= 0.4:
        direction = "long_bias" if mean_reversion_score > 0 else "short_bias"

    edge = clip(direction_score * (0.55 + 0.45 * confidence))
    if direction == "short_bias":
        edge = -abs(edge)
    elif direction == "long_bias":
        edge = abs(edge)
    else:
        edge = 0.0

    metrics = {
        "adx": adx,
        "adx_pos": adx_pos,
        "adx_neg": adx_neg,
        "atr_pct": atr_percent,
        "rsi": rsi_value,
        "stoch": stoch_value,
        "macd_hist": macd_value,
        "macd_accel": macd_accel,
        "bb_pct": bb_pct,
        "bb_width": bb_width,
        "volume_ratio": vol_ratio,
        "liquidity_score": liq_score,
        "momentum_5": momentum_5,
        "momentum_20": momentum_20,
        "roc3": roc3,
        "zscore_20": zscore_20,
    }

    return MarketRegimeSnapshot(
        regime=regime,
        direction=direction,
        confidence=confidence,
        edge=edge,
        trend_score=trend_score,
        breakout_score=breakout_score,
        mean_reversion_score=mean_reversion_score,
        volatility_score=volatility_score,
        liquidity_score=liq_score,
        adx=adx,
        atr_pct=atr_percent,
        realised_vol_20d=realised_volatility(close),
        rsi=rsi_value,
        volume_ratio=vol_ratio,
        notes=tuple(notes),
        metrics=metrics,
    )


def regime_alignment_for_side(snapshot: MarketRegimeSnapshot, side: str) -> float:
    side_norm = str(side or "").strip().lower()
    if side_norm in {"buy", "long", "long_bias"}:
        return float(np.clip(0.5 + (snapshot.edge / 2.0), 0.0, 1.0))
    if side_norm in {"sell", "short", "short_bias"}:
        return float(np.clip(0.5 - (snapshot.edge / 2.0), 0.0, 1.0))
    return float(np.clip(snapshot.confidence, 0.0, 1.0))


def market_regime_features(df: pd.DataFrame) -> dict[str, float]:
    snapshot = infer_market_regime(df)
    payload = dict(snapshot.metrics)
    payload.update({"regime_confidence": snapshot.confidence, "regime_edge": snapshot.edge})
    return payload


from app.quant.technical import detect_regime, technical_score  # noqa: E402

__all__ = [
    "AverageTrueRange",
    "MarketRegimeSnapshot",
    "PortfolioRegimeSnapshot",
    "detect_regime",
    "infer_market_regime",
    "infer_portfolio_risk_regime",
    "market_regime_features",
    "regime_alignment_for_side",
    "technical_score",
]
