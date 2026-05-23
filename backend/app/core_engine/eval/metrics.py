from __future__ import annotations

from typing import Any

import numpy as np


def confidence_bucket_alignment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"buckets": [], "brier_score": None}

    scored = []
    for row in rows:
        confidence = float(row.get("confidence", 0.0))
        outcome = float(row.get("outcome", 0.0))
        predicted = float(np.clip((row.get("score", 0.0) + 1.0) / 2.0, 0.0, 1.0))
        scored.append({"confidence": confidence, "outcome": outcome, "predicted": predicted})

    buckets: list[dict[str, Any]] = []
    for low, high in ((0.0, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)):
        bucket = [x for x in scored if low <= x["confidence"] < high]
        if not bucket:
            continue
        buckets.append(
            {
                "range": f"[{low:.1f},{min(high, 1.0):.1f})",
                "count": len(bucket),
                "avg_confidence": float(np.mean([x["confidence"] for x in bucket])),
                "avg_outcome": float(np.mean([x["outcome"] for x in bucket])),
            }
        )

    brier = float(np.mean([(x["predicted"] - x["outcome"]) ** 2 for x in scored]))
    return {"buckets": buckets, "brier_score": brier}
