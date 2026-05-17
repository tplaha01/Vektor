from __future__ import annotations

from app.utils.common import clamp
from app.utils.sentiment import sentiment_model_name, sentiment_model_status, sentiment_score


def news_sentiment_score(news_items: list[dict[str, object]]) -> float:
    texts = [str(item.get("headline") or "") for item in news_items if item.get("headline")]
    return clamp(sentiment_score(texts))


__all__ = [
    "news_sentiment_score",
    "sentiment_model_name",
    "sentiment_model_status",
    "sentiment_score",
]
