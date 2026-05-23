from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.config import get_settings
from app.data.fundamentals import get_fundamentals
from app.data.market_data import FEED
from app.data.news import latest_news
from app.ml.alpha_model import ensure_model, model_status, predict
from app.quant.regime import infer_market_regime
from app.quant.statistics import adx_triplet, atr_pct, bollinger_position, macd_hist, rsi, stoch, volume_ratio
from app.utils.common import clamp
from app.utils.sentiment import sentiment_model_name, sentiment_score


@dataclass
class EngineResult:
    symbol: str
    timestamp: str
    score: float
    action: str
    confidence: float
    subscores: dict[str, float]
    model: dict[str, Any]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'score': round(float(self.score), 6),
            'action': self.action,
            'confidence': round(float(self.confidence), 6),
            'subscores': {k: round(float(v), 6) for k, v in self.subscores.items()},
            'model': self.model,
            'diagnostics': self.diagnostics,
        }


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        pass
    return default


def _normalize_hist(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=['ts', 'open', 'high', 'low', 'close', 'volume'])

    cols = {str(c).lower(): c for c in df.columns}
    rename: dict[str, str] = {}
    for src, dst in (
        ('date', 'ts'),
        ('datetime', 'ts'),
        ('ts', 'ts'),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
    ):
        if src in cols:
            rename[cols[src]] = dst

    out = df.rename(columns=rename).copy()
    needed = ['ts', 'open', 'high', 'low', 'close', 'volume']
    for col in needed:
        if col not in out.columns:
            out[col] = np.nan
    out = out[needed]
    for col in ('open', 'high', 'low', 'close', 'volume'):
        out[col] = pd.to_numeric(out[col], errors='coerce')
    out['ts'] = pd.to_datetime(out['ts'], utc=True, errors='coerce')
    out = out.dropna(subset=['close', 'high', 'low']).sort_values('ts').reset_index(drop=True)
    return out


def _fundamental_domain_weights(symbol: str) -> dict[str, float]:
    sym = str(symbol or '').upper().strip()
    tech = {'AAPL', 'MSFT', 'NVDA', 'AMD', 'AMZN', 'GOOGL', 'META', 'TSLA'}
    finance = {'JPM', 'BAC', 'GS', 'MS', 'WFC', 'C'}
    energy = {'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'USO', 'UNG'}
    if sym in tech:
        return {'growth': 0.42, 'margin': 0.32, 'leverage': 0.16, 'valuation': 0.10}
    if sym in finance:
        return {'growth': 0.28, 'margin': 0.22, 'leverage': 0.30, 'valuation': 0.20}
    if sym in energy:
        return {'growth': 0.24, 'margin': 0.28, 'leverage': 0.28, 'valuation': 0.20}
    return {'growth': 0.34, 'margin': 0.30, 'leverage': 0.20, 'valuation': 0.16}


def _project_fundamentals(fund: dict[str, Any], hist: pd.DataFrame) -> tuple[dict[str, float], float]:
    growth = _safe_float(fund.get('revenue_growth'), 0.05)
    gross = _safe_float(fund.get('gross_margin'), 0.35)
    oper = _safe_float(fund.get('oper_margin'), 0.18)
    debt = _safe_float(fund.get('debt_to_equity'), 1.0)
    pe = _safe_float(fund.get('pe'), 22.0)

    drift = 0.0
    if len(hist) >= 60:
        prev = _safe_float(hist['close'].iloc[-21], 0.0)
        now = _safe_float(hist['close'].iloc[-1], 0.0)
        ret_20 = (now - prev) / (prev + 1e-9)
        drift = float(np.clip(ret_20 * 0.35, -0.08, 0.08))

    projected = {
        'revenue_growth_fwd': float(np.clip(growth + drift, -0.2, 0.8)),
        'gross_margin_fwd': float(np.clip(gross + drift * 0.2, 0.05, 0.85)),
        'oper_margin_fwd': float(np.clip(oper + drift * 0.25, -0.2, 0.6)),
        'debt_to_equity_fwd': float(np.clip(debt - drift * 0.6, 0.0, 6.0)),
        'pe_fwd': float(np.clip(pe - drift * 40.0, 2.0, 120.0)),
    }
    confidence = float(np.clip(0.55 + abs(drift) * 2.0, 0.55, 0.9))
    return projected, confidence


def _fundamental_score(symbol: str, fundamentals: dict[str, Any], hist: pd.DataFrame) -> tuple[float, dict[str, Any]]:
    projected, projection_conf = _project_fundamentals(fundamentals, hist)
    w = _fundamental_domain_weights(symbol)

    growth_term = float(np.clip(projected['revenue_growth_fwd'] / 0.25, -1.0, 1.0))
    margin = (projected['gross_margin_fwd'] + projected['oper_margin_fwd']) / 2.0
    margin_term = float(np.clip((margin - 0.2) / 0.35, -1.0, 1.0))
    leverage_term = float(np.clip(1.0 - (projected['debt_to_equity_fwd'] / 2.5), -1.0, 1.0))
    valuation_term = float(np.clip(1.0 - (projected['pe_fwd'] / 35.0), -1.0, 1.0))

    score = clamp(
        w['growth'] * growth_term
        + w['margin'] * margin_term
        + w['leverage'] * leverage_term
        + w['valuation'] * valuation_term
    )
    detail = {
        'projection': projected,
        'projection_confidence': projection_conf,
        'weights': w,
        'terms': {
            'growth': growth_term,
            'margin': margin_term,
            'leverage': leverage_term,
            'valuation': valuation_term,
        },
    }
    return score, detail


def _technical_score(hist: pd.DataFrame) -> tuple[float, dict[str, Any]]:
    if len(hist) < 80:
        return 0.0, {'reason': 'insufficient_history'}

    c = hist['close'].astype(float)
    h = hist['high'].astype(float)
    l = hist['low'].astype(float)
    v = hist['volume'].astype(float).fillna(0.0)

    snap = infer_market_regime(hist)
    adx, adx_pos, adx_neg = adx_triplet(c, h, l)
    atrp = atr_pct(c, h, l)
    bb_pct, bb_width = bollinger_position(c)
    rsi_val = rsi(c)
    stoch_val = stoch(h, l, c)
    macd_val, macd_accel = macd_hist(c)
    volr = volume_ratio(v)

    breakout_high = float(c.iloc[-1] > h.tail(20).max())
    breakout_low = float(c.iloc[-1] < l.tail(20).min())
    stop_hunt_down = float(l.iloc[-1] < l.tail(10).min() and c.iloc[-1] > c.iloc[-2])
    stop_hunt_up = float(h.iloc[-1] > h.tail(10).max() and c.iloc[-1] < c.iloc[-2])
    liquidity_trap = stop_hunt_down - stop_hunt_up

    direction = clamp(
        0.28 * _safe_float(snap.edge)
        + 0.18 * clamp((adx_pos - adx_neg) / 30.0)
        + 0.15 * clamp((rsi_val - 50.0) / 25.0)
        + 0.12 * clamp(macd_val * 8.0)
        + 0.10 * clamp((stoch_val - 50.0) / 30.0)
        + 0.09 * clamp((bb_pct - 0.5) * 2.0)
        + 0.08 * clamp(liquidity_trap)
    )
    stability = float(np.clip(1.0 - (abs(atrp - 0.025) / 0.05), 0.0, 1.0))
    confidence = float(np.clip(0.45 + 0.3 * stability + 0.25 * min(1.0, abs(direction)), 0.0, 1.0))

    detail = {
        'regime': snap.regime,
        'regime_edge': _safe_float(snap.edge),
        'adx': adx,
        'atr_pct': atrp,
        'rsi': rsi_val,
        'stoch': stoch_val,
        'macd_hist': macd_val,
        'macd_accel': macd_accel,
        'bb_pct': bb_pct,
        'bb_width': bb_width,
        'volume_ratio': volr,
        'breakout_up': breakout_high,
        'breakout_down': breakout_low,
        'liquidity_trap': liquidity_trap,
        'confidence': confidence,
    }
    return direction, detail


def _sentiment_score(symbol: str, news: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    if not news:
        return 0.0, {'reason': 'no_news', 'model': sentiment_model_name()}

    source_weights = {
        'reuters': 1.0,
        'bloomberg': 1.0,
        'wsj': 0.95,
        'cnbc': 0.9,
        'finnhub': 0.75,
        'yahoo': 0.65,
        'reddit': 0.55,
        'twitter': 0.5,
        'x': 0.5,
    }

    now = datetime.now(timezone.utc)
    weighted: list[float] = []
    rows: list[dict[str, Any]] = []
    for item in news[:24]:
        headline = str(item.get('headline') or '').strip()
        if not headline:
            continue
        src = str(item.get('source') or 'unknown').strip().lower()
        src_w = source_weights.get(src, 0.6)
        published_at_raw = item.get('published_at')
        age_h = 12.0
        try:
            parsed = pd.to_datetime(published_at_raw, utc=True)
            age_h = max(0.0, (now - parsed.to_pydatetime()).total_seconds() / 3600.0)
        except Exception:
            pass

        time_w = float(math.exp(-age_h / 18.0))
        s = float(np.clip(sentiment_score([headline]), -1.0, 1.0))
        w = src_w * time_w
        weighted.append(s * w)
        rows.append({'source': src, 'sentiment': s, 'weight': w, 'age_hours': round(age_h, 3)})

    if not rows:
        return 0.0, {'reason': 'no_usable_news', 'model': sentiment_model_name()}

    denom = sum(r['weight'] for r in rows) + 1e-9
    agg = float(np.clip(sum(weighted) / denom, -1.0, 1.0))
    count_24 = sum(1 for r in rows if r['age_hours'] <= 24)
    horizon_24h = float(
        np.clip(
            sum(r['sentiment'] for r in rows if r['age_hours'] <= 24) / max(1, count_24),
            -1.0,
            1.0,
        )
    )
    crowd_rows = [r for r in rows if r['source'] in {'reddit', 'twitter', 'x'}]
    crowd_proxy = float(np.clip(sum(r['sentiment'] for r in crowd_rows) / max(1, len(crowd_rows)), -1.0, 1.0))

    detail = {
        'symbol': symbol,
        'model': sentiment_model_name(),
        'headline_count': len(rows),
        'horizon_24h': horizon_24h,
        'crowd_proxy': crowd_proxy,
        'source_breakdown': rows,
    }
    return agg, detail


def _sequence_proxy_alpha(hist: pd.DataFrame) -> float:
    if len(hist) < 30:
        return 0.0
    c = hist['close'].astype(float)
    returns = np.log(c / c.shift(1)).dropna().tail(30)
    if returns.empty:
        return 0.0
    trend = float(np.tanh(returns.mean() * 20.0))
    persistence = 0.0
    if len(returns) > 3:
        corr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        if math.isfinite(float(corr)):
            persistence = float(np.tanh(float(corr)))
    return clamp(0.7 * trend + 0.3 * persistence)


def _regime_logit_alpha(tech_detail: dict[str, Any]) -> float:
    edge = _safe_float(tech_detail.get('regime_edge'))
    adx = _safe_float(tech_detail.get('adx'))
    vol_ratio = _safe_float(tech_detail.get('volume_ratio'), 1.0)
    x = 1.6 * edge + 0.6 * ((adx - 20.0) / 20.0) + 0.25 * (vol_ratio - 1.0)
    prob_up = 1.0 / (1.0 + math.exp(-x))
    return clamp((prob_up - 0.5) * 2.0)


def _select_ml_model(hist: pd.DataFrame, tech_detail: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
    ensure_model()
    st = model_status()
    has_lgbm = bool(st.get('ready'))

    regime = str(tech_detail.get('regime') or 'RANGE')
    vol = _safe_float(tech_detail.get('atr_pct'), 0.02)

    candidates: list[tuple[str, float]] = []
    candidates.append(('regime_logit', _regime_logit_alpha(tech_detail)))
    candidates.append(('sequence_proxy', _sequence_proxy_alpha(hist)))
    if has_lgbm:
        try:
            ml_alpha = float(predict(hist[['ts', 'open', 'high', 'low', 'close', 'volume']].copy()))
        except Exception:
            ml_alpha = 0.0
        candidates.append(('lgbm_alpha', clamp(ml_alpha)))

    if regime in {'TREND_UP', 'TREND_DOWN', 'BREAKOUT_UP', 'BREAKOUT_DOWN'} and has_lgbm:
        selected = 'lgbm_alpha'
    elif vol > 0.04:
        selected = 'regime_logit'
    else:
        selected = 'sequence_proxy' if not has_lgbm else 'lgbm_alpha'

    values = {k: v for k, v in candidates}
    selected_alpha = float(values.get(selected, 0.0))
    diagnostics = {
        'status': st,
        'candidates': values,
        'selected': selected,
        'regime': regime,
        'atr_pct': vol,
    }
    return selected, selected_alpha, diagnostics


def deterministic_signal(symbol: str) -> EngineResult:
    settings = get_settings()
    sym = str(symbol or '').upper().strip()

    hist = _normalize_hist(FEED.history(sym, bars=320))
    if len(hist) < 80:
        return EngineResult(
            symbol=sym,
            timestamp=_utc_iso(),
            score=0.0,
            action='hold',
            confidence=0.0,
            subscores={'technical': 0.0, 'fundamental': 0.0, 'sentiment': 0.0, 'ml': 0.0},
            model={'selected': 'none', 'mandatory_ml': True, 'ready': False},
            diagnostics={'reason': 'insufficient_market_history', 'bars': len(hist)},
        )

    technical, tech_detail = _technical_score(hist)
    fundamentals = dict(get_fundamentals(sym) or {})
    fundamental, fundamental_detail = _fundamental_score(sym, fundamentals, hist)
    sentiment, sentiment_detail = _sentiment_score(sym, latest_news(sym, limit=24))
    selected_model, ml_alpha, ml_diag = _select_ml_model(hist, tech_detail)

    score = clamp(0.58 * ml_alpha + 0.22 * technical + 0.12 * fundamental + 0.08 * sentiment)
    confidence = float(np.clip(0.5 + 0.25 * abs(ml_alpha) + 0.15 * abs(technical) + 0.1 * abs(fundamental), 0.0, 1.0))

    vol = _safe_float(tech_detail.get('atr_pct'), 0.02)
    if vol > settings.VOL_THRESHOLD:
        action = 'hold'
    else:
        action = 'buy' if score > settings.BUY_THRESHOLD else ('sell' if score < settings.SELL_THRESHOLD else 'hold')

    diagnostics = {
        'volatility': vol,
        'technical': tech_detail,
        'fundamental': fundamental_detail,
        'sentiment': sentiment_detail,
        'ml': ml_diag,
    }
    return EngineResult(
        symbol=sym,
        timestamp=_utc_iso(),
        score=score,
        action=action,
        confidence=confidence,
        subscores={'technical': technical, 'fundamental': fundamental, 'sentiment': sentiment, 'ml': ml_alpha},
        model={'selected': selected_model, 'mandatory_ml': True, 'ready': bool((ml_diag.get('status') or {}).get('ready', False))},
        diagnostics=diagnostics,
    )

