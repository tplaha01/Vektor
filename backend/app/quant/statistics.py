from __future__ import annotations

import numpy as np
import pandas as pd

from app.quant.common import safe_float

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import ADXIndicator, MACD
    from ta.volatility import AverageTrueRange, BollingerBands
except Exception:
    RSIIndicator = None
    StochasticOscillator = None
    ADXIndicator = None
    MACD = None
    AverageTrueRange = None
    BollingerBands = None


def fallback_rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff().fillna(0.0)
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean().iloc[-1]
    avg_loss = loss.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean().iloc[-1]
    if avg_loss <= 1e-9:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def fallback_stoch(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> float:
    highest = high.rolling(window).max().iloc[-1]
    lowest = low.rolling(window).min().iloc[-1]
    spread = max(safe_float(highest) - safe_float(lowest), 1e-9)
    return 100.0 * (safe_float(close.iloc[-1]) - safe_float(lowest)) / spread


def fallback_macd_hist(close: pd.Series) -> tuple[float, float]:
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    last = safe_float(hist.iloc[-1])
    accel = safe_float(hist.iloc[-1] - hist.iloc[-3] if len(hist) >= 3 else hist.iloc[-1])
    return last, accel


def fallback_adx_triplet(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) -> tuple[float, float, float]:
    prev_close = close.shift(1)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=close.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=close.index)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean() / (atr + 1e-9)
    minus_di = 100.0 * minus_dm.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean() / (atr + 1e-9)
    dx = 100.0 * (plus_di - minus_di).abs() / ((plus_di + minus_di).abs() + 1e-9)
    adx = dx.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean()
    return safe_float(adx.iloc[-1]), safe_float(plus_di.iloc[-1]), safe_float(minus_di.iloc[-1])


def fallback_bollinger_position(close: pd.Series, window: int = 20, dev: float = 2.0) -> tuple[float, float]:
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = mid + dev * std
    lower = mid - dev * std
    width = safe_float(upper.iloc[-1] - lower.iloc[-1])
    pct = (safe_float(close.iloc[-1]) - safe_float(lower.iloc[-1])) / (width + 1e-9)
    width_ratio = width / (safe_float(mid.iloc[-1]) + 1e-9)
    return pct, width_ratio


def atr_pct(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) -> float:
    if AverageTrueRange is not None:
        atr = AverageTrueRange(high, low, close, window=window, fillna=True).average_true_range().iloc[-1]
        return safe_float(atr) / (safe_float(close.iloc[-1]) + 1e-9)
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / max(int(window), 1), adjust=False, min_periods=window).mean().iloc[-1]
    return safe_float(atr) / (safe_float(close.iloc[-1]) + 1e-9)


def adx_triplet(close: pd.Series, high: pd.Series, low: pd.Series) -> tuple[float, float, float]:
    if ADXIndicator is None:
        return fallback_adx_triplet(close, high, low)
    ind = ADXIndicator(high, low, close, window=14, fillna=True)
    adx = safe_float(ind.adx().iloc[-1])
    adx_pos = safe_float(ind.adx_pos().iloc[-1])
    adx_neg = safe_float(ind.adx_neg().iloc[-1])
    if adx <= 0 and adx_pos == 0 and adx_neg == 0:
        return fallback_adx_triplet(close, high, low)
    return adx, adx_pos, adx_neg


def rsi(close: pd.Series) -> float:
    if RSIIndicator is None:
        return fallback_rsi(close)
    value = safe_float(RSIIndicator(close=close, window=14, fillna=True).rsi().iloc[-1], 50.0)
    return value if value > 0 else fallback_rsi(close)


def stoch(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
    if StochasticOscillator is None:
        return fallback_stoch(high, low, close)
    value = safe_float(StochasticOscillator(high, low, close, window=14, smooth_window=3, fillna=True).stoch().iloc[-1], 50.0)
    return value if value > 0 else fallback_stoch(high, low, close)


def macd_hist(close: pd.Series) -> tuple[float, float]:
    if MACD is None:
        return fallback_macd_hist(close)
    ind = MACD(close, window_slow=26, window_fast=12, window_sign=9, fillna=True)
    hist = ind.macd_diff()
    last = safe_float(hist.iloc[-1])
    accel = safe_float(hist.iloc[-1] - hist.iloc[-3] if len(hist) >= 3 else hist.iloc[-1])
    if last == 0 and accel == 0:
        return fallback_macd_hist(close)
    return last, accel


def bollinger_position(close: pd.Series) -> tuple[float, float]:
    if BollingerBands is None:
        return fallback_bollinger_position(close)
    bb = BollingerBands(close=close, window=20, window_dev=2, fillna=True)
    upper = safe_float(bb.bollinger_hband().iloc[-1])
    lower = safe_float(bb.bollinger_lband().iloc[-1])
    mid = safe_float(bb.bollinger_mavg().iloc[-1])
    width = max(upper - lower, 1e-9)
    pct = safe_float((close.iloc[-1] - lower) / width)
    width_ratio = safe_float(width / (mid + 1e-9))
    if width <= 0 or pct == 0.5:
        return fallback_bollinger_position(close)
    return pct, width_ratio


def volume_ratio(volume: pd.Series) -> float:
    mean = safe_float(volume.rolling(20).mean().iloc[-1])
    if mean <= 0:
        return 1.0
    return safe_float(volume.iloc[-1] / (mean + 1e-9), 1.0)


def liquidity_score(close: pd.Series, volume: pd.Series) -> float:
    avg_dollar_volume = 0.0
    if len(close) and len(volume):
        avg_dollar_volume = float(
            sum(max(0.0, c) * max(0.0, v) for c, v in zip(close.tail(20), volume.tail(20)))
            / max(1, min(len(close.tail(20)), len(volume.tail(20))))
        )
    return float(np.clip(avg_dollar_volume / 150_000_000.0, 0.05, 1.0))


def realised_volatility(close: pd.Series, window: int = 20, annualization: int = 252) -> float:
    if len(close) <= 1:
        return 0.0
    return safe_float(np.log(close / close.shift(1)).dropna().tail(window).std() * np.sqrt(annualization))


_fallback_rsi = fallback_rsi
_fallback_stoch = fallback_stoch
_fallback_macd_hist = fallback_macd_hist
_fallback_adx_triplet = fallback_adx_triplet
_fallback_bollinger_position = fallback_bollinger_position
_atr_pct = atr_pct
_adx_triplet = adx_triplet
_rsi = rsi
_stoch = stoch
_macd_hist = macd_hist
_bollinger_position = bollinger_position
_volume_ratio = volume_ratio
_liquidity_score = liquidity_score
