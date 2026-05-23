from __future__ import annotations

from app.config import get_settings
from app.core_engine import run_core_engine


def hybrid_signal(symbol: str, profile: str | None = None) -> dict:
    settings = get_settings()
    result = run_core_engine(symbol, profile=profile)
    payload = result.to_dict()

    existing_weights = dict(payload.get('weights') or {})
    payload['weights'] = {
        'technical': float(existing_weights.get('technical', settings.TECH_WEIGHT)),
        'fundamental': float(existing_weights.get('fundamental', settings.FUND_WEIGHT)),
        'sentiment': float(existing_weights.get('sentiment', settings.SENT_WEIGHT)),
        'ml_alpha': float(existing_weights.get('ml_alpha', settings.ML_WEIGHT)),
    }
    payload['ml_ready'] = bool(payload.get('model', {}).get('ready', False))
    payload['sentiment_model'] = str(payload.get('diagnostics', {}).get('sentiment', {}).get('model', 'VADER'))
    payload['volatility'] = (
        payload.get('diagnostics', {}).get('technical', {}).get('atr_pct')
        or payload.get('diagnostics', {}).get('volatility')
    )

    subscores = dict(payload.get('subscores') or {})
    if 'ml' in subscores and 'ml_alpha' not in subscores:
        subscores['ml_alpha'] = subscores['ml']
    payload['subscores'] = subscores
    return payload

