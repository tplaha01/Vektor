from __future__ import annotations

import logging
import threading
from typing import List

# ---------------------------------------------------------------------------
# Dual-mode sentiment scorer
#
# Primary:  FinBERT (ProsusAI/finbert) - finance-domain BERT, stronger than
#           VADER for market headlines. Loaded lazily in a background thread
#           so startup is not blocked.
#
# Fallback: VADER - used immediately if FinBERT is not loaded yet, or if
#           transformers/torch are unavailable.
# ---------------------------------------------------------------------------

_finbert_pipeline = None
_finbert_loading = False
_finbert_lock = threading.Lock()
_finbert_available = False
_log = logging.getLogger("alfred.sentiment")


def _load_finbert() -> None:
    """Load FinBERT in a background thread."""
    global _finbert_pipeline, _finbert_available, _finbert_loading
    try:
        from transformers import pipeline

        _log.info("loading FinBERT model ProsusAI/finbert")
        _finbert_pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            top_k=None,  # return all labels with scores
            device=-1,  # CPU only
            truncation=True,
            max_length=512,
        )
        _finbert_available = True
        _log.info("FinBERT loaded; sentiment model upgraded to finance-domain pipeline")
    except Exception as exc:
        _log.warning("FinBERT load failed; using VADER fallback: %s", exc)
        _finbert_available = False
    finally:
        _finbert_loading = False


def _ensure_finbert() -> None:
    """Trigger background load once."""
    global _finbert_loading
    with _finbert_lock:
        if not _finbert_available and not _finbert_loading:
            _finbert_loading = True
            t = threading.Thread(target=_load_finbert, daemon=True, name="finbert-loader")
            t.start()


def _vader_score(texts: List[str]) -> float:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        analyzer = SentimentIntensityAnalyzer()
        scores = [analyzer.polarity_scores(t)["compound"] for t in texts]
        return float(sum(scores) / max(len(scores), 1))
    except Exception:
        return 0.0


def _finbert_score(texts: List[str]) -> float:
    """
    FinBERT maps to: positive=+1, negative=-1, neutral=0
    Each headline scored individually then averaged.
    Confidence-weighted: high-confidence neutral headlines pull toward 0.
    """
    label_map = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
    scores = []
    for text in texts[:16]:  # cap at 16 headlines to stay fast
        try:
            result = _finbert_pipeline(text[:512])
            # result is list of lists: [[{label, score}, ...]]
            preds = result[0] if isinstance(result[0], list) else result
            best = max(preds, key=lambda x: x["score"])
            signed = label_map.get(best["label"].lower(), 0.0)
            # weight by confidence
            scores.append(signed * best["score"])
        except Exception:
            continue
    return float(sum(scores) / max(len(scores), 1)) if scores else 0.0


def sentiment_score(texts: List[str]) -> float:
    """
    Public API - always returns a float in [-1, 1].
    Uses FinBERT if loaded, VADER otherwise.
    Triggers FinBERT background load on first call.
    """
    if not texts:
        return 0.0

    _ensure_finbert()  # kick off load if not started

    if _finbert_available and _finbert_pipeline is not None:
        return _finbert_score(texts)

    return _vader_score(texts)


def sentiment_model_name() -> str:
    """Returns which model is currently active."""
    return "FinBERT" if _finbert_available else "VADER"


def sentiment_model_status() -> dict:
    """Structured status for startup checks and health endpoints."""
    return {
        "active_model": sentiment_model_name(),
        "finbert_available": _finbert_available,
        "finbert_loading": _finbert_loading,
    }
