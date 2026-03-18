from __future__ import annotations
"""
Feature engineering pipeline for the ML alpha model.

All features are computed from raw OHLCV data and return a single
flat dict of floats that LightGBM can consume directly.

Feature families:
  - Price-based:     returns at multiple horizons, log-price ratios
  - Trend:           SMA/EMA crossover ratios, ADX
  - Momentum:        RSI, MACD histogram, Stochastic, ROC
  - Volatility:      ATR%, BB width, realised vol
  - Volume:          OBV slope, volume Z-score, VWAP deviation
  - Mean reversion:  Z-score of price vs rolling mean
  - Regime:          high-vol flag, trending flag
"""

import numpy as np
import pandas as pd
from typing import Dict


def _safe(val, default=0.0) -> float:
    try:
        v = float(val)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def build_features(df: pd.DataFrame) -> Dict[str, float]:
    """
    Given a DataFrame with columns [ts, open, high, low, close, volume],
    returns a flat dict of ML features computed from the latest bar.
    Requires at least 60 rows.
    """
    if len(df) < 60:
        return {}

    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    v = df["volume"].astype(float)

    feat: Dict[str, float] = {}

    # ── Price returns ────────────────────────────────────────────────────
    for n in [1, 2, 3, 5, 10, 20]:
        if len(c) > n:
            ret = (c.iloc[-1] - c.iloc[-(n+1)]) / (c.iloc[-(n+1)] + 1e-9)
            feat[f"ret_{n}d"] = _safe(ret)

    # Log price ratio to 52-week high/low
    roll52 = min(len(c), 252)
    feat["pct_from_52w_high"] = _safe((c.iloc[-1] - c.tail(roll52).max()) / (c.tail(roll52).max() + 1e-9))
    feat["pct_from_52w_low"]  = _safe((c.iloc[-1] - c.tail(roll52).min()) / (c.tail(roll52).min() + 1e-9))

    # ── Trend features ───────────────────────────────────────────────────
    for w in [10, 20, 50]:
        sma = c.rolling(w).mean().iloc[-1]
        feat[f"sma{w}_ratio"] = _safe(c.iloc[-1] / (sma + 1e-9))

    ema12 = c.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = c.ewm(span=26, adjust=False).mean().iloc[-1]
    feat["ema_crossover"] = _safe(ema12 / (ema26 + 1e-9))

    try:
        from ta.trend import ADXIndicator
        adx_ind = ADXIndicator(h, l, c, window=14, fillna=True)
        feat["adx"]     = _safe(adx_ind.adx().iloc[-1])
        feat["adx_pos"] = _safe(adx_ind.adx_pos().iloc[-1])
        feat["adx_neg"] = _safe(adx_ind.adx_neg().iloc[-1])
        feat["adx_diff"] = feat["adx_pos"] - feat["adx_neg"]
    except Exception:
        pass

    # ── Momentum features ────────────────────────────────────────────────
    try:
        from ta.momentum import RSIIndicator, StochasticOscillator
        rsi = RSIIndicator(close=c, window=14, fillna=True).rsi()
        feat["rsi_14"]    = _safe(rsi.iloc[-1])
        feat["rsi_slope"] = _safe(rsi.iloc[-1] - rsi.iloc[-5])

        stoch = StochasticOscillator(h, l, c, window=14, smooth_window=3, fillna=True).stoch()
        feat["stoch_14"] = _safe(stoch.iloc[-1])
    except Exception:
        pass

    try:
        from ta.trend import MACD
        macd = MACD(c, window_slow=26, window_fast=12, window_sign=9, fillna=True)
        feat["macd_hist"]       = _safe(macd.macd_diff().iloc[-1])
        feat["macd_hist_slope"] = _safe(macd.macd_diff().iloc[-1] - macd.macd_diff().iloc[-3])
        feat["macd_line"]       = _safe(macd.macd().iloc[-1])
        feat["macd_signal"]     = _safe(macd.macd_signal().iloc[-1])
    except Exception:
        pass

    for n in [3, 5, 10]:
        roc = (c.iloc[-1] - c.iloc[-(n+1)]) / (c.iloc[-(n+1)] + 1e-9)
        feat[f"roc_{n}d"] = _safe(roc)

    # ── Volatility features ──────────────────────────────────────────────
    try:
        from ta.volatility import BollingerBands, AverageTrueRange
        bb = BollingerBands(c, window=20, window_dev=2, fillna=True)
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_mid   = bb.bollinger_mavg().iloc[-1]
        bb_width = bb_upper - bb_lower
        feat["bb_pct"]   = _safe((c.iloc[-1] - bb_lower) / (bb_width + 1e-9))
        feat["bb_width"] = _safe(bb_width / (bb_mid + 1e-9))

        atr = AverageTrueRange(h, l, c, window=14, fillna=True).average_true_range().iloc[-1]
        feat["atr_pct"] = _safe(atr / (c.iloc[-1] + 1e-9))
    except Exception:
        pass

    # Realised volatility (20-day)
    log_ret = np.log(c / c.shift(1)).dropna()
    feat["realised_vol_20d"] = _safe(log_ret.tail(20).std() * np.sqrt(252))

    # ── Volume features ──────────────────────────────────────────────────
    try:
        from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
        obv = OnBalanceVolumeIndicator(c, v, fillna=True).on_balance_volume()
        feat["obv_slope_5d"] = _safe((obv.iloc[-1] - obv.iloc[-6]) / (abs(obv.iloc[-6]) + 1e-9))

        vwap = VolumeWeightedAveragePrice(h, l, c, v, window=14, fillna=True).volume_weighted_average_price()
        feat["vwap_dev"] = _safe((c.iloc[-1] - vwap.iloc[-1]) / (vwap.iloc[-1] + 1e-9))
    except Exception:
        pass

    vol_mean = v.rolling(20).mean().iloc[-1]
    vol_std  = v.rolling(20).std().iloc[-1]
    feat["vol_zscore"] = _safe((v.iloc[-1] - vol_mean) / (vol_std + 1e-9))
    feat["vol_ratio_5d"] = _safe(v.iloc[-1] / (v.tail(5).mean() + 1e-9))

    # ── Mean reversion ───────────────────────────────────────────────────
    roll_mean = c.rolling(20).mean().iloc[-1]
    roll_std  = c.rolling(20).std().iloc[-1]
    feat["zscore_20d"] = _safe((c.iloc[-1] - roll_mean) / (roll_std + 1e-9))

    roll_mean_60 = c.rolling(60).mean().iloc[-1]
    roll_std_60  = c.rolling(60).std().iloc[-1]
    feat["zscore_60d"] = _safe((c.iloc[-1] - roll_mean_60) / (roll_std_60 + 1e-9))

    # ── Regime flags ─────────────────────────────────────────────────────
    feat["high_vol_regime"] = float(feat.get("atr_pct", 0) > 0.025)
    feat["trending_regime"] = float(feat.get("adx", 0) > 25)
    feat["above_sma50"]     = float(feat.get("sma50_ratio", 1.0) > 1.0)

    return feat
