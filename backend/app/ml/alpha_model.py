from __future__ import annotations
"""
LightGBM Alpha Model
====================
Predicts a forward 5-day return direction (up/down) from the feature
vector built by features.py.

Alpha signal:
  - Output: probability of up move, scaled to [-1, +1]
  - score = (prob_up - 0.5) * 2
  - Clipped to [-1, 1]
"""

import logging
import threading
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    joblib = None  # type: ignore[assignment]

from app.ml.features import build_features

MODEL_PATH = Path(__file__).parent / "lgbm_alpha.pkl"
FEATURE_NAMES_PATH = Path(__file__).parent / "feature_names.pkl"

_model = None
_feature_names = None
_model_lock = threading.Lock()
_model_ready = False
_training = False
logger = logging.getLogger("alfred.ml.alpha_model")


def _train_model() -> None:
    """
    Train LightGBM on historical data for the watchlist.
    Uses TimeSeriesSplit to avoid lookahead bias.
    Saves model to disk when joblib is available.
    """
    global _model, _feature_names, _model_ready, _training

    try:
        import lightgbm as lgb  # type: ignore
        import yfinance as yf  # type: ignore
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import TimeSeriesSplit

        logger.info("Training LightGBM alpha model")

        watchlist = ["AAPL", "MSFT", "NVDA", "SPY", "TSLA", "AMZN", "GOOGL", "META", "JPM", "GS"]
        forward_days = 5
        all_rows = []

        for symbol in watchlist:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="2y", interval="1d")
                if df.empty or len(df) < 100:
                    continue

                df = df.reset_index()
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                df = df.rename(
                    columns={
                        "Date": "ts",
                        "Open": "open",
                        "High": "high",
                        "Low": "low",
                        "Close": "close",
                        "Volume": "volume",
                    }
                )

                for idx in range(60, len(df) - forward_days):
                    window = df.iloc[: idx + 1].copy()
                    feat = build_features(window)
                    if not feat:
                        continue

                    fwd_ret = (df["close"].iloc[idx + forward_days] - df["close"].iloc[idx]) / (
                        df["close"].iloc[idx] + 1e-9
                    )
                    feat["_label"] = int(fwd_ret > 0.0)
                    feat["_symbol"] = symbol
                    all_rows.append(feat)

            except Exception as exc:
                logger.warning("Skipping %s during alpha training: %s", symbol, exc)

        if len(all_rows) < 200:
            logger.warning("Not enough training data for alpha model; staying neutral")
            return

        data = pd.DataFrame(all_rows)
        feature_cols = [c for c in data.columns if not c.startswith("_")]
        x_vals = data[feature_cols].fillna(0.0)
        y_vals = data["_label"]

        tscv = TimeSeriesSplit(n_splits=5)
        auc_scores = []

        for train_idx, val_idx in tscv.split(x_vals):
            x_train, x_val = x_vals.iloc[train_idx], x_vals.iloc[val_idx]
            y_train, y_val = y_vals.iloc[train_idx], y_vals.iloc[val_idx]

            clf = lgb.LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=4,
                num_leaves=15,
                min_child_samples=20,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=0.1,
                random_state=42,
                verbose=-1,
            )
            clf.fit(x_train, y_train)
            prob = clf.predict_proba(x_val)[:, 1]
            if len(np.unique(y_val)) > 1:
                auc_scores.append(roc_auc_score(y_val, prob))

        avg_auc = float(np.mean(auc_scores)) if auc_scores else 0.5

        final_model = lgb.LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=4,
            num_leaves=15,
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=0.1,
            random_state=42,
            verbose=-1,
        )
        final_model.fit(x_vals, y_vals)

        with _model_lock:
            _model = final_model
            _feature_names = feature_cols
            _model_ready = True

        if joblib is not None:
            joblib.dump(final_model, MODEL_PATH)
            joblib.dump(feature_cols, FEATURE_NAMES_PATH)

        logger.info(
            "Alpha model ready; features=%s samples=%s auc=%.4f persisted=%s",
            len(feature_cols),
            len(all_rows),
            avg_auc,
            bool(joblib is not None),
        )
    except Exception as exc:
        logger.warning("LightGBM training failed; alpha remains neutral: %s", exc)
    finally:
        _training = False


def _load_or_train() -> None:
    global _model, _feature_names, _model_ready, _training

    if joblib is not None and MODEL_PATH.exists() and FEATURE_NAMES_PATH.exists():
        try:
            with _model_lock:
                _model = joblib.load(MODEL_PATH)
                _feature_names = joblib.load(FEATURE_NAMES_PATH)
                _model_ready = True
                _training = False
            logger.info("Alpha model loaded from disk")
            return
        except Exception as exc:
            logger.warning("Failed to load saved alpha model: %s; retraining", exc)

    _training = True
    trainer = threading.Thread(target=_train_model, daemon=True, name="lgbm-trainer")
    trainer.start()


def ensure_model() -> None:
    if not _model_ready and not _training:
        _load_or_train()


def predict(df: pd.DataFrame) -> float:
    """
    Given OHLCV DataFrame, return alpha signal in [-1, 1].
    Returns 0.0 if model not ready yet.
    """
    if not _model_ready or _model is None:
        return 0.0

    if "ts" not in df.columns and "date" in df.columns:
        df = df.rename(columns={"date": "ts"})

    feat = build_features(df)
    if not feat:
        return 0.0

    try:
        with _model_lock:
            x_vals = pd.DataFrame([feat]).reindex(columns=_feature_names, fill_value=0.0)
            prob_up = float(_model.predict_proba(x_vals)[0][1])

        score = (prob_up - 0.5) * 2.0
        return float(np.clip(score, -1.0, 1.0))
    except Exception as exc:
        logger.warning("Alpha prediction failed; returning neutral: %s", exc)
        return 0.0


def model_status() -> dict:
    # Expose a consistent status: ready model should not report active training.
    training_now = bool(_training and not _model_ready)
    return {
        "ready": _model_ready,
        "training": training_now,
        "features": len(_feature_names) if _feature_names else 0,
        "path": str(MODEL_PATH) if MODEL_PATH.exists() else None,
        "joblib_available": bool(joblib is not None),
    }
