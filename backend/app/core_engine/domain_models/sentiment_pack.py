from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.core_engine.contracts import DomainModelOutput, EngineInputSnapshot
from app.utils.sentiment import sentiment_model_name, sentiment_score


def run_sentiment_pack(snapshot: EngineInputSnapshot) -> DomainModelOutput:
    news = snapshot.news
    if not news:
        return DomainModelOutput(
            name="sentiment",
            alpha=0.0,
            uncertainty=0.95,
            diagnostics={"reason": "no_news", "model": sentiment_model_name()},
        )

    source_weights = {
        "reuters": 1.0,
        "bloomberg": 1.0,
        "wsj": 0.95,
        "cnbc": 0.9,
        "finnhub": 0.75,
        "yahoo": 0.65,
        "reddit": 0.55,
        "twitter": 0.5,
        "x": 0.5,
    }

    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    weighted_values: list[float] = []
    for item in news[:24]:
        headline = str(item.get("headline") or "").strip()
        if not headline:
            continue
        src = str(item.get("source") or "unknown").strip().lower()
        src_weight = source_weights.get(src, 0.6)
        age_h = 12.0
        try:
            published_ts = pd.to_datetime(item.get("published_at"), utc=True).to_pydatetime()
            if published_ts.tzinfo is None:
                published_ts = published_ts.replace(tzinfo=timezone.utc)
            age_h = max(0.0, (now - published_ts).total_seconds() / 3600.0)
        except Exception:
            pass

        time_weight = float(math.exp(-age_h / 18.0))
        sentiment = float(np.clip(sentiment_score([headline]), -1.0, 1.0))
        weight = src_weight * time_weight
        weighted_values.append(sentiment * weight)
        rows.append({"source": src, "sentiment": sentiment, "weight": weight, "age_hours": round(age_h, 3)})

    if not rows:
        return DomainModelOutput(
            name="sentiment",
            alpha=0.0,
            uncertainty=0.95,
            diagnostics={"reason": "no_usable_news", "model": sentiment_model_name()},
        )

    weight_total = sum(r["weight"] for r in rows) + 1e-9
    alpha = float(np.clip(sum(weighted_values) / weight_total, -1.0, 1.0))
    crowd_rows = [r for r in rows if r["source"] in {"reddit", "twitter", "x"}]
    crowd_sentiment = float(np.clip(sum(r["sentiment"] for r in crowd_rows) / max(1, len(crowd_rows)), -1.0, 1.0))
    confidence = float(np.clip(0.45 + 0.25 * min(1.0, len(rows) / 12.0) + 0.3 * abs(alpha), 0.0, 1.0))
    uncertainty = float(np.clip(1.0 - confidence, 0.05, 1.0))

    return DomainModelOutput(
        name="sentiment",
        alpha=alpha,
        uncertainty=uncertainty,
        diagnostics={
            "model": sentiment_model_name(),
            "headline_count": len(rows),
            "crowd_proxy": crowd_sentiment,
            "source_breakdown": rows,
        },
    )
