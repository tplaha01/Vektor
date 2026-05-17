from __future__ import annotations

import pandas as pd

from app.ml.alpha_model import ensure_model, model_status, predict
from app.ml.features import build_features


def ml_alpha_score(df: pd.DataFrame) -> float:
    return predict(df)


__all__ = ["build_features", "ensure_model", "ml_alpha_score", "model_status", "predict"]
