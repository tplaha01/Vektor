from __future__ import annotations
import threading
from typing import List

# ---------------------------------------------------------------------------
# Dual-mode sentiment scorer
#
# Primary:  FinBERT (ProsusAI/finbert) — finance-domain BERT, far superior
#           to VADER for market headlines. Loaded lazily in a background
#           thread so startup isn't blocked.
#
# Fallback: VADER — runs immediately if FinBERT hasn't loaded yet, or if
#           transformers/torch aren't installed.
# ---------------------------------------------------------------------------

_finbert_pipeline = None
_finbert_loading = False
_finbert_lock = threading.Lock()
_finbert_available = False


def _load_finbert():
    """Load FinBERT in a background thread."""
    global _finbert_pipeline, _finbert_available, _finbert_loading
    try:
        from transformers import pipeline
        print("⏳ Loading FinBERT (ProsusAI/finbert)...")
        _finbert_pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            top_k=None,           # return all labels with scores
            device=-1,            # CPU — no GPU required
            truncation=True,
            max_length=512,
        )
        _finbert_available = True
        print("✅ FinBERT loaded — NLP sentiment now finance-grade")
    except Exception as e:
        print(f"⚠️ FinBERT load failed: {e} — using VADER fallback")
        _finbert_available = False
    finally:
        _finbert_loading = False


def _ensure_finbert():
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
    for text in texts[:16]:   # cap at 16 headlines to stay fast
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
    Public API — always returns a float in [-1, 1].
    Uses FinBERT if loaded, VADER otherwise.
    Triggers FinBERT background load on first call.
    """
    if not texts:
        return 0.0

    _ensure_finbert()   # kick off load if not started

    if _finbert_available and _finbert_pipeline is not None:
        return _finbert_score(texts)

    return _vader_score(texts)


def sentiment_model_name() -> str:
    """Returns which model is currently active."""
    return "FinBERT" if _finbert_available else "VADER"
