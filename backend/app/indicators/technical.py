from __future__ import annotations
import logging
import pandas as pd
import numpy as np

try:
    from ta.trend import ADXIndicator, MACD
    from ta.volatility import BollingerBands, AverageTrueRange
    from ta.volume import OnBalanceVolumeIndicator
    from ta.momentum import StochasticOscillator, RSIIndicator
    _TA_AVAILABLE = True
except Exception:
    ADXIndicator = None
    MACD = None
    BollingerBands = None
    AverageTrueRange = None
    OnBalanceVolumeIndicator = None
    StochasticOscillator = None
    RSIIndicator = None
    _TA_AVAILABLE = False

_log = logging.getLogger("alfred.indicators.technical")


def detect_regime(c, h, l, v, adx_val, adx_pos, adx_neg):
    atr_val = AverageTrueRange(h, l, c, window=14, fillna=True).average_true_range().iloc[-1]
    atr_pct = float(atr_val / (c.iloc[-1] + 1e-9))
    if atr_pct > 0.045:
        return 'HIGH_VOL', atr_pct

    vol_mean  = v.rolling(20).mean().iloc[-1]
    vol_ratio = float(v.iloc[-1] / (vol_mean + 1e-9))
    high_20   = h.rolling(20).max().iloc[-2]
    low_20    = l.rolling(20).min().iloc[-2]
    if vol_ratio > 2.0:
        if c.iloc[-1] > high_20:
            return 'BREAKOUT_UP', atr_pct
        if c.iloc[-1] < low_20:
            return 'BREAKOUT_DOWN', atr_pct

    if adx_val > 25:
        return ('TREND_UP' if adx_pos > adx_neg else 'TREND_DOWN'), atr_pct

    return 'RANGE', atr_pct


def _trend_score(c, h, l, v, adx_val, adx_pos, adx_neg, direction) -> float:
    sma20 = c.rolling(20).mean().iloc[-1]
    sma50 = c.rolling(50).mean().iloc[-1]
    ema12 = c.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = c.ewm(span=26, adjust=False).mean().iloc[-1]

    price_vs_sma20 = 1.0 if c.iloc[-1] > sma20 else -1.0
    price_vs_sma50 = 1.0 if c.iloc[-1] > sma50 else -1.0
    ema_cross      = 1.0 if ema12 > ema26 else -1.0
    adx_strength   = min(adx_val / 50.0, 1.0)
    adx_dir        = 1.0 if adx_pos > adx_neg else -1.0

    macd_ind   = MACD(close=c, window_slow=26, window_fast=12, window_sign=9, fillna=True)
    macd_hist  = macd_ind.macd_diff()
    macd_norm  = float(np.clip(macd_hist.iloc[-1] / (c.iloc[-1] + 1e-9) * 100, -1.0, 1.0))
    macd_accel = 1.0 if macd_hist.iloc[-1] > macd_hist.iloc[-2] else -1.0

    rsi = float(RSIIndicator(close=c, window=14, fillna=True).rsi().iloc[-1])
    if direction == 'TREND_UP':
        rsi_score = 1.0 if 45 < rsi < 72 else (0.4 if rsi >= 72 else -0.3)
    else:
        rsi_score = -1.0 if 28 < rsi < 55 else (-0.4 if rsi <= 28 else 0.3)

    obv = OnBalanceVolumeIndicator(c, v, fillna=True).on_balance_volume()
    obv_slope = 1.0 if (obv.iloc[-1] - obv.iloc[-6]) > 0 else -1.0

    raw = (
        0.25 * price_vs_sma20 +
        0.15 * price_vs_sma50 +
        0.20 * ema_cross +
        0.20 * adx_dir * adx_strength +
        0.15 * macd_norm * (1.1 if macd_accel > 0 else 0.9) +
        0.05 * rsi_score
    )
    # Only return signal if OBV confirms direction
    if (raw > 0 and obv_slope < 0) or (raw < 0 and obv_slope > 0):
        raw *= 0.7
    return float(np.clip(raw, -1.0, 1.0))


def _mean_reversion_score(c, h, l, v) -> float:
    """
    Only fires on genuine extremes — NOT in the middle of the band.
    This eliminates the noise trades that caused 25 stop-outs.
    """
    bb = BollingerBands(close=c, window=20, window_dev=2, fillna=True)
    bb_upper = float(bb.bollinger_hband().iloc[-1])
    bb_lower = float(bb.bollinger_lband().iloc[-1])
    bb_width = bb_upper - bb_lower
    bb_pct   = float((c.iloc[-1] - bb_lower) / (bb_width + 1e-9))

    rsi = float(RSIIndicator(close=c, window=14, fillna=True).rsi().iloc[-1])
    stoch = float(StochasticOscillator(h, l, c, window=14, smooth_window=3, fillna=True).stoch().iloc[-1])

    roll_mean = c.rolling(20).mean().iloc[-1]
    roll_std  = c.rolling(20).std().iloc[-1]
    zscore    = float((c.iloc[-1] - roll_mean) / (roll_std + 1e-9))

    # REQUIRE multiple extreme conditions — no more weak signal trades
    bullish_conditions = sum([
        bb_pct < 0.08,        # price at/below lower band
        rsi < 32,             # oversold
        stoch < 22,           # stoch oversold
        zscore < -1.8,        # 1.8 std below mean
    ])
    bearish_conditions = sum([
        bb_pct > 0.92,
        rsi > 68,
        stoch > 78,
        zscore > 1.8,
    ])

    if bullish_conditions >= 2:
        # Scale by how many conditions fire
        score = 0.5 + (bullish_conditions - 2) * 0.2
        return float(min(score, 1.0))
    if bearish_conditions >= 2:
        score = -(0.5 + (bearish_conditions - 2) * 0.2)
        return float(max(score, -1.0))

    # Not extreme enough — sit out
    return 0.0


def _breakout_score(c, h, l, v, direction) -> float:
    vol_mean  = v.rolling(20).mean().iloc[-1]
    vol_ratio = float(v.iloc[-1] / (vol_mean + 1e-9))
    vol_score = float(np.clip((vol_ratio - 1.5) / 1.5, 0.0, 1.0))

    roc3 = float((c.iloc[-1] - c.iloc[-4]) / (c.iloc[-4] + 1e-9))
    roc_score = float(np.clip(abs(roc3) * 20, 0.0, 1.0))

    macd_ind   = MACD(close=c, window_slow=26, window_fast=12, window_sign=9, fillna=True)
    macd_score = 1.0 if macd_ind.macd_diff().iloc[-1] > 0 else -1.0

    dir_mult = 1.0 if direction == 'BREAKOUT_UP' else -1.0
    raw = dir_mult * (0.50 * vol_score + 0.30 * roc_score + 0.20 * (macd_score * dir_mult))
    return float(np.clip(raw, -1.0, 1.0))


def _high_vol_score(c, h, l, v) -> float:
    rsi = float(RSIIndicator(close=c, window=14, fillna=True).rsi().iloc[-1])
    # Only trade extreme RSI in high-vol — tighter thresholds
    if rsi < 22:
        return 0.6
    if rsi > 80:
        return -0.6
    return 0.0


def technical_score(df: pd.DataFrame, debug: bool = False):
    if len(df) < 60:
        return 0.0

    if not _TA_AVAILABLE:
        # Minimal deterministic fallback when `ta` package is unavailable.
        c = df["close"].astype(float)
        momentum_5 = float((c.iloc[-1] - c.iloc[-6]) / (c.iloc[-6] + 1e-9))
        sma20 = float(c.rolling(20).mean().iloc[-1])
        sma50 = float(c.rolling(50).mean().iloc[-1])
        trend = 1.0 if sma20 > sma50 else -1.0
        price_position = 1.0 if float(c.iloc[-1]) > sma20 else -1.0
        raw = (0.55 * trend) + (0.25 * price_position) + (0.20 * float(np.clip(momentum_5 * 12, -1.0, 1.0)))
        final = float(np.clip(raw, -1.0, 1.0))
        if debug:
            return {
                "regime": "FALLBACK_NO_TA",
                "adx": None,
                "atr_pct": None,
                "score": round(final, 4),
            }
        _log.debug("technical_score_fallback_no_ta")
        return final

    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    v = df["volume"].astype(float)

    adx_ind = ADXIndicator(h, l, c, window=14, fillna=True)
    adx_val = float(adx_ind.adx().iloc[-1])
    adx_pos = float(adx_ind.adx_pos().iloc[-1])
    adx_neg = float(adx_ind.adx_neg().iloc[-1])

    regime, atr_pct = detect_regime(c, h, l, v, adx_val, adx_pos, adx_neg)

    if regime in ('TREND_UP', 'TREND_DOWN'):
        score = _trend_score(c, h, l, v, adx_val, adx_pos, adx_neg, regime)
    elif regime in ('BREAKOUT_UP', 'BREAKOUT_DOWN'):
        score = _breakout_score(c, h, l, v, regime)
    elif regime == 'HIGH_VOL':
        score = _high_vol_score(c, h, l, v)
    else:
        score = _mean_reversion_score(c, h, l, v)

    final = float(np.clip(score, -1.0, 1.0))

    if debug:
        return {"regime": regime, "adx": round(adx_val, 2),
                "atr_pct": round(atr_pct * 100, 3), "score": round(final, 4)}
    return final
