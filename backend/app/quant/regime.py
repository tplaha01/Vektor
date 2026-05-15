from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import ADXIndicator, MACD
    from ta.volatility import AverageTrueRange, BollingerBands
    _TA_AVAILABLE = True
except Exception:
    RSIIndicator = None
    StochasticOscillator = None
    ADXIndicator = None
    MACD = None
    AverageTrueRange = None
    BollingerBands = None
    _TA_AVAILABLE = False


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else default
    except Exception:
        return default


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return float(np.clip(float(value), low, high))


def _trend_sign(value: float, threshold: float = 0.0) -> float:
    if value > threshold:
        return 1.0
    if value < -threshold:
        return -1.0
    return 0.0


def _price_group(symbol: str, asset_class: str, metadata: dict[str, object] | None = None) -> str:
    meta = metadata if isinstance(metadata, dict) else {}
    explicit = str(meta.get("correlation_group") or "").strip().lower()
    if explicit:
        return explicit
    normalized_symbol = str(symbol or "").upper().strip()
    normalized_asset_class = str(asset_class or "").strip().lower()
    if normalized_asset_class == "forex":
        return "fx_usd"
    if normalized_asset_class == "crypto":
        return "crypto_beta"
    if normalized_asset_class == "commodities":
        return "commodity_macro"
    if normalized_symbol in {"SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMD", "AMZN", "GOOGL", "META", "TSLA", "XLK"}:
        return "equity_growth"
    if normalized_symbol in {"XLF", "JPM", "BAC", "GS"}:
        return "equity_financials"
    if normalized_symbol in {"XLE", "USO", "UNG", "GLD", "SLV"}:
        return "commodity_macro"
    if normalized_symbol in {"TLT", "IEF", "SHY"}:
        return "rates_duration"
    return f"{normalized_asset_class or 'unknown'}_general"


@dataclass(frozen=True)
class MarketRegimeSnapshot:
    regime: str
    direction: str
    confidence: float
    edge: float
    trend_score: float
    breakout_score: float
    mean_reversion_score: float
    volatility_score: float
    liquidity_score: float
    adx: float | None = None
    atr_pct: float | None = None
    realised_vol_20d: float | None = None
    rsi: float | None = None
    volume_ratio: float | None = None
    notes: tuple[str, ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "direction": self.direction,
            "confidence": round(float(self.confidence), 4),
            "edge": round(float(self.edge), 4),
            "trend_score": round(float(self.trend_score), 4),
            "breakout_score": round(float(self.breakout_score), 4),
            "mean_reversion_score": round(float(self.mean_reversion_score), 4),
            "volatility_score": round(float(self.volatility_score), 4),
            "liquidity_score": round(float(self.liquidity_score), 4),
            "adx": None if self.adx is None else round(float(self.adx), 4),
            "atr_pct": None if self.atr_pct is None else round(float(self.atr_pct), 6),
            "realised_vol_20d": None if self.realised_vol_20d is None else round(float(self.realised_vol_20d), 6),
            "rsi": None if self.rsi is None else round(float(self.rsi), 4),
            "volume_ratio": None if self.volume_ratio is None else round(float(self.volume_ratio), 4),
            "notes": list(self.notes),
            "metrics": {key: round(float(value), 6) for key, value in self.metrics.items()},
        }


@dataclass(frozen=True)
class PortfolioRegimeSnapshot:
    macro_risk_level: str
    risk_score: float
    symbol_exposure_ratio: float
    correlated_group_exposure_ratio: float
    asset_class_usage_ratio: float
    cash_reserve_ratio: float
    leverage_ratio: float
    notes: tuple[str, ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "macro_risk_level": self.macro_risk_level,
            "risk_score": round(float(self.risk_score), 4),
            "symbol_exposure_ratio": round(float(self.symbol_exposure_ratio), 4),
            "correlated_group_exposure_ratio": round(float(self.correlated_group_exposure_ratio), 4),
            "asset_class_usage_ratio": round(float(self.asset_class_usage_ratio), 4),
            "cash_reserve_ratio": round(float(self.cash_reserve_ratio), 4),
            "leverage_ratio": round(float(self.leverage_ratio), 4),
            "notes": list(self.notes),
            "metrics": {key: round(float(value), 6) for key, value in self.metrics.items()},
        }


def _series_close_high_low_volume(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)
    return close, high, low, volume


def _fallback_rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff().fillna(0.0)
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean().iloc[-1]
    avg_loss = loss.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean().iloc[-1]
    if avg_loss <= 1e-9:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _fallback_stoch(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> float:
    highest = high.rolling(window).max().iloc[-1]
    lowest = low.rolling(window).min().iloc[-1]
    spread = max(_safe_float(highest) - _safe_float(lowest), 1e-9)
    return 100.0 * (_safe_float(close.iloc[-1]) - _safe_float(lowest)) / spread


def _fallback_macd_hist(close: pd.Series) -> tuple[float, float]:
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    last = _safe_float(hist.iloc[-1])
    accel = _safe_float(hist.iloc[-1] - hist.iloc[-3] if len(hist) >= 3 else hist.iloc[-1])
    return last, accel


def _fallback_adx_triplet(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) -> tuple[float, float, float]:
    prev_close = close.shift(1)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=close.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=close.index)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean() / (atr + 1e-9)
    minus_di = 100.0 * minus_dm.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean() / (atr + 1e-9)
    dx = 100.0 * (plus_di - minus_di).abs() / ((plus_di + minus_di).abs() + 1e-9)
    adx = dx.ewm(alpha=1 / max(window, 1), adjust=False, min_periods=window).mean()
    return _safe_float(adx.iloc[-1]), _safe_float(plus_di.iloc[-1]), _safe_float(minus_di.iloc[-1])


def _fallback_bollinger_position(close: pd.Series, window: int = 20, dev: float = 2.0) -> tuple[float, float]:
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = mid + dev * std
    lower = mid - dev * std
    width = _safe_float((upper.iloc[-1] - lower.iloc[-1]))
    pct = (_safe_float(close.iloc[-1]) - _safe_float(lower.iloc[-1])) / (width + 1e-9)
    width_ratio = width / (_safe_float(mid.iloc[-1]) + 1e-9)
    return pct, width_ratio


def _atr_pct(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) -> float:
    if AverageTrueRange is not None:
        atr = AverageTrueRange(high, low, close, window=window, fillna=True).average_true_range().iloc[-1]
        return _safe_float(atr) / (_safe_float(close.iloc[-1]) + 1e-9)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / max(int(window), 1), adjust=False, min_periods=window).mean().iloc[-1]
    return _safe_float(atr) / (_safe_float(close.iloc[-1]) + 1e-9)


def _adx_triplet(close: pd.Series, high: pd.Series, low: pd.Series) -> tuple[float, float, float]:
    if ADXIndicator is None:
        return _fallback_adx_triplet(close, high, low)
    ind = ADXIndicator(high, low, close, window=14, fillna=True)
    adx = _safe_float(ind.adx().iloc[-1])
    adx_pos = _safe_float(ind.adx_pos().iloc[-1])
    adx_neg = _safe_float(ind.adx_neg().iloc[-1])
    if adx <= 0 and adx_pos == 0 and adx_neg == 0:
        return _fallback_adx_triplet(close, high, low)
    return adx, adx_pos, adx_neg


def _rsi(close: pd.Series) -> float:
    if RSIIndicator is None:
        return _fallback_rsi(close)
    value = _safe_float(RSIIndicator(close=close, window=14, fillna=True).rsi().iloc[-1], 50.0)
    return value if value > 0 else _fallback_rsi(close)


def _stoch(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
    if StochasticOscillator is None:
        return _fallback_stoch(high, low, close)
    value = _safe_float(StochasticOscillator(high, low, close, window=14, smooth_window=3, fillna=True).stoch().iloc[-1], 50.0)
    return value if value > 0 else _fallback_stoch(high, low, close)


def _macd_hist(close: pd.Series) -> tuple[float, float]:
    if MACD is None:
        return _fallback_macd_hist(close)
    ind = MACD(close, window_slow=26, window_fast=12, window_sign=9, fillna=True)
    hist = ind.macd_diff()
    last = _safe_float(hist.iloc[-1])
    accel = _safe_float(hist.iloc[-1] - hist.iloc[-3] if len(hist) >= 3 else hist.iloc[-1])
    if last == 0 and accel == 0:
        return _fallback_macd_hist(close)
    return last, accel


def _bollinger_position(close: pd.Series) -> tuple[float, float]:
    if BollingerBands is None:
        return _fallback_bollinger_position(close)
    bb = BollingerBands(close=close, window=20, window_dev=2, fillna=True)
    upper = _safe_float(bb.bollinger_hband().iloc[-1])
    lower = _safe_float(bb.bollinger_lband().iloc[-1])
    mid = _safe_float(bb.bollinger_mavg().iloc[-1])
    width = max(upper - lower, 1e-9)
    pct = _safe_float((close.iloc[-1] - lower) / width)
    width_ratio = _safe_float(width / (mid + 1e-9))
    if width <= 0 or pct == 0.5:
        return _fallback_bollinger_position(close)
    return pct, width_ratio


def _volume_ratio(volume: pd.Series) -> float:
    mean = _safe_float(volume.rolling(20).mean().iloc[-1])
    if mean <= 0:
        return 1.0
    return _safe_float(volume.iloc[-1] / (mean + 1e-9), 1.0)


def _liquidity_score(close: pd.Series, volume: pd.Series) -> float:
    avg_dollar_volume = 0.0
    if len(close) and len(volume):
        avg_dollar_volume = float(
            sum(max(0.0, c) * max(0.0, v) for c, v in zip(close.tail(20), volume.tail(20)))
            / max(1, min(len(close.tail(20)), len(volume.tail(20))))
        )
    return float(np.clip(avg_dollar_volume / 150_000_000.0, 0.05, 1.0))


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

    close, high, low, volume = _series_close_high_low_volume(df)
    adx, adx_pos, adx_neg = _adx_triplet(close, high, low)
    atr_pct = _atr_pct(close, high, low)
    rsi = _rsi(close)
    stoch = _stoch(high, low, close)
    macd_hist, macd_accel = _macd_hist(close)
    bb_pct, bb_width = _bollinger_position(close)
    volume_ratio = _volume_ratio(volume)
    liquidity_score = _liquidity_score(close, volume)

    sma20 = _safe_float(close.rolling(20).mean().iloc[-1])
    sma50 = _safe_float(close.rolling(50).mean().iloc[-1])
    ema12 = _safe_float(close.ewm(span=12, adjust=False).mean().iloc[-1])
    ema26 = _safe_float(close.ewm(span=26, adjust=False).mean().iloc[-1])
    close_px = _safe_float(close.iloc[-1])
    prev_5 = _safe_float(close.iloc[-6] if len(close) > 5 else close.iloc[0], close_px)
    prev_20 = _safe_float(close.iloc[-21] if len(close) > 20 else close.iloc[0], close_px)
    momentum_5 = (close_px - prev_5) / (prev_5 + 1e-9)
    momentum_20 = (close_px - prev_20) / (prev_20 + 1e-9)
    roc3 = (close_px - _safe_float(close.iloc[-4] if len(close) > 3 else close.iloc[0], close_px)) / (close_px + 1e-9)
    zscore_20 = _safe_float((close_px - close.rolling(20).mean().iloc[-1]) / (close.rolling(20).std().iloc[-1] + 1e-9))

    trend_score = _clip(
        (
            0.22 * _trend_sign(close_px - sma20)
            + 0.16 * _trend_sign(close_px - sma50)
            + 0.16 * _trend_sign(ema12 - ema26)
            + 0.14 * _trend_sign(adx_pos - adx_neg) * min(adx / 40.0, 1.0)
            + 0.16 * _clip(momentum_5 * 12.0)
            + 0.16 * _clip(momentum_20 * 8.0)
        )
    )

    breakout_up = max(0.0, (close_px / (_safe_float(high.tail(20).max()) + 1e-9)) - 1.0)
    breakout_down = max(0.0, (_safe_float(low.tail(20).min()) / (close_px + 1e-9)) - 1.0)
    breakout_score = _clip(
        (
            0.38 * _clip((volume_ratio - 1.0) / 1.5, 0.0, 1.0)
            + 0.34 * _clip(max(breakout_up, breakout_down) * 22.0, 0.0, 1.0)
            + 0.16 * _clip(abs(roc3) * 20.0, 0.0, 1.0)
            + 0.12 * _trend_sign(breakout_up - breakout_down)
        ) * (1.0 if breakout_up >= breakout_down else -1.0 if breakout_down > breakout_up else 0.0)
    )

    bullish_conditions = sum([
        bb_pct < 0.10,
        rsi < 32.0,
        stoch < 24.0,
        zscore_20 < -1.75,
    ])
    bearish_conditions = sum([
        bb_pct > 0.90,
        rsi > 68.0,
        stoch > 76.0,
        zscore_20 > 1.75,
    ])
    if bullish_conditions >= 2:
        mean_reversion_score = float(min(1.0, 0.5 + 0.18 * (bullish_conditions - 2)))
    elif bearish_conditions >= 2:
        mean_reversion_score = float(max(-1.0, -(0.5 + 0.18 * (bearish_conditions - 2))))
    else:
        mean_reversion_score = 0.0

    volatility_score = float(np.clip(1.0 - abs(atr_pct - 0.025) / 0.04, 0.0, 1.0))

    direction_score = (
        0.44 * trend_score
        + 0.24 * breakout_score
        + 0.20 * mean_reversion_score
        + 0.07 * _clip((momentum_5 * 10.0))
        + 0.05 * _clip((bb_width - 0.04) / 0.08)
    )

    confidence = float(np.clip(
        (
            0.34 * abs(trend_score)
            + 0.24 * abs(breakout_score)
            + 0.18 * abs(mean_reversion_score)
            + 0.14 * volatility_score
            + 0.10 * liquidity_score
        ),
        0.0,
        1.0,
    ))

    notes: list[str] = []
    if adx >= 25.0:
        notes.append("adx_trend")
    if volume_ratio >= 1.5:
        notes.append("volume_expansion")
    if volatility_score >= 0.75:
        notes.append("volatility_orderly")
    if bullish_conditions >= 2 or bearish_conditions >= 2:
        notes.append("mean_reversion_extreme")
    if abs(direction_score) < 0.12:
        notes.append("low_directional_edge")

    if volatility_score >= 0.80 and abs(direction_score) < 0.22:
        regime = "HIGH_VOL"
    elif abs(breakout_score) >= 0.50 and volume_ratio >= 1.35:
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

    edge = _clip(direction_score * (0.55 + 0.45 * confidence))
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
        "atr_pct": atr_pct,
        "rsi": rsi,
        "stoch": stoch,
        "macd_hist": macd_hist,
        "macd_accel": macd_accel,
        "bb_pct": bb_pct,
        "bb_width": bb_width,
        "volume_ratio": volume_ratio,
        "liquidity_score": liquidity_score,
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
        liquidity_score=liquidity_score,
        adx=adx,
        atr_pct=atr_pct,
        realised_vol_20d=_safe_float(np.log(close / close.shift(1)).dropna().tail(20).std() * np.sqrt(252)) if len(close) > 1 else 0.0,
        rsi=rsi,
        volume_ratio=volume_ratio,
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
    payload.update(
        {
            "regime_confidence": snapshot.confidence,
            "regime_edge": snapshot.edge,
        }
    )
    return payload


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


@dataclass(frozen=True)
class _PortfolioState:
    symbol_exposure: float
    correlated_group_exposure: float
    asset_class_usage: float
    cash_reserve: float
    leverage: float
    risk_score: float
    macro_risk_level: str
    notes: tuple[str, ...]


def infer_portfolio_risk_regime(
    *,
    symbol: str,
    asset_class: str,
    positions: list[dict[str, object]],
    equity: float,
    notional: float,
    metadata: dict[str, object] | None = None,
) -> PortfolioRegimeSnapshot:
    meta = metadata if isinstance(metadata, dict) else {}
    constraints = meta.get("allocation_constraints") if isinstance(meta.get("allocation_constraints"), dict) else {}
    normalized_symbol = str(symbol or "").upper().strip()
    normalized_asset_class = str(asset_class or "").strip().lower()
    correlation_group = _price_group(normalized_symbol, normalized_asset_class, meta)

    symbol_exposure = 0.0
    correlated_group_exposure = 0.0
    gross_exposure = 0.0
    for position in positions:
        position_symbol = str(position.get("symbol") or "").upper().strip()
        position_asset_class = str(position.get("asset_class") or normalized_asset_class or "equities").strip().lower()
        position_meta = position.get("metadata") if isinstance(position.get("metadata"), dict) else {}
        position_market_value = _safe_float(position.get("market_value"))
        if position_market_value <= 0:
            position_market_value = max(0.0, _safe_float(position.get("qty")) * _safe_float(position.get("market_price")))
        gross_exposure += max(0.0, position_market_value)
        if position_symbol == normalized_symbol:
            symbol_exposure += position_market_value
        if _price_group(position_symbol, position_asset_class, position_meta) == correlation_group:
            correlated_group_exposure += position_market_value

    available_cash = _safe_float(meta.get("available_cash"))
    min_cash_reserve_pct = _safe_float(constraints.get("min_cash_reserve_pct"))
    asset_allocated = _safe_float(meta.get("asset_class_budget_allocated_usd"))
    asset_used = _safe_float(meta.get("asset_class_budget_used_usd"))
    projected_symbol_exposure = symbol_exposure + max(0.0, notional)
    projected_group_exposure = correlated_group_exposure + max(0.0, notional)
    projected_asset_usage = asset_used + max(0.0, notional)
    projected_cash = available_cash - max(0.0, notional)
    cash_reserve_ratio = (projected_cash / equity) if equity > 0 else 0.0
    symbol_ratio = (projected_symbol_exposure / equity) if equity > 0 else 0.0
    group_ratio = (projected_group_exposure / equity) if equity > 0 else 0.0
    asset_usage_ratio = (projected_asset_usage / asset_allocated) if asset_allocated > 0 else 0.0
    leverage_ratio = (gross_exposure / equity) if equity > 0 else 0.0

    risk_score = float(np.clip(
        (
            0.30 * np.clip(symbol_ratio / 0.25, 0.0, 1.0)
            + 0.25 * np.clip(group_ratio / 0.30, 0.0, 1.0)
            + 0.20 * np.clip(asset_usage_ratio / 0.90, 0.0, 1.0)
            + 0.15 * np.clip((min_cash_reserve_pct - cash_reserve_ratio) / 0.05, 0.0, 1.0)
            + 0.10 * np.clip((leverage_ratio - 1.0) / 0.5, 0.0, 1.0)
        ),
        0.0,
        1.0,
    ))

    notes: list[str] = []
    if cash_reserve_ratio < min_cash_reserve_pct:
        notes.append("cash_reserve_breach")
    if symbol_ratio >= 0.22:
        notes.append("symbol_concentration_high")
    elif symbol_ratio >= 0.15:
        notes.append("symbol_concentration_elevated")
    if group_ratio >= 0.30:
        notes.append("correlated_group_high")
    elif group_ratio >= 0.22:
        notes.append("correlated_group_elevated")
    if asset_usage_ratio >= 0.90:
        notes.append("asset_budget_near_full")
    elif asset_usage_ratio >= 0.75:
        notes.append("asset_budget_tight")
    if leverage_ratio >= 1.20:
        notes.append("portfolio_leverage_high")

    if risk_score >= 0.75:
        macro_risk_level = "risk_off"
    elif risk_score >= 0.55:
        macro_risk_level = "stressed"
    elif risk_score >= 0.35 or meta.get("event_risk_active", False):
        macro_risk_level = "volatile"
    else:
        macro_risk_level = "normal"

    return PortfolioRegimeSnapshot(
        macro_risk_level=macro_risk_level,
        risk_score=risk_score,
        symbol_exposure_ratio=symbol_ratio,
        correlated_group_exposure_ratio=group_ratio,
        asset_class_usage_ratio=asset_usage_ratio,
        cash_reserve_ratio=cash_reserve_ratio,
        leverage_ratio=leverage_ratio,
        notes=tuple(notes),
        metrics={
            "gross_exposure": gross_exposure,
            "projected_symbol_exposure": projected_symbol_exposure,
            "projected_group_exposure": projected_group_exposure,
            "projected_asset_usage": projected_asset_usage,
            "cash_reserve_ratio": cash_reserve_ratio,
            "min_cash_reserve_ratio": min_cash_reserve_pct,
            "available_cash": available_cash,
        },
    )
