from __future__ import annotations

from app.config import get_settings
from app.strategies.deterministic_ml_engine import deterministic_signal


def hybrid_signal(symbol: str) -> dict:
    settings = get_settings()
    result = deterministic_signal(symbol)
    payload = result.to_dict()

    payload['weights'] = {
        'technical': settings.TECH_WEIGHT,
        'fundamental': settings.FUND_WEIGHT,
        'sentiment': settings.SENT_WEIGHT,
        'ml_alpha': settings.ML_WEIGHT,
    }
    payload['ml_ready'] = bool(payload.get('model', {}).get('ready', False))
    payload['sentiment_model'] = str(payload.get('diagnostics', {}).get('sentiment', {}).get('model', 'VADER'))
    payload['volatility'] = payload.get('diagnostics', {}).get('volatility')

    subscores = dict(payload.get('subscores') or {})
    if 'ml' in subscores and 'ml_alpha' not in subscores:
        subscores['ml_alpha'] = subscores['ml']
    payload['subscores'] = subscores
    return payload

