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
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    joblib = None  # type: ignore[assignment]

from app.ml.features import build_features
from app.ml.training_data import load_warehouse_training_dataset
from app.quant.probability import probability_to_alpha

MODEL_PATH = Path(__file__).parent / "lgbm_alpha.pkl"
FEATURE_NAMES_PATH = Path(__file__).parent / "feature_names.pkl"
METADATA_PATH = Path(__file__).parent / "lgbm_alpha_metadata.json"

_model = None
_feature_names = None
_model_metrics = {}
_model_lock = threading.Lock()
_model_ready = False
_training = False
logger = logging.getLogger("alfred.ml.alpha_model")


def _legacy_yfinance_rows() -> list[dict]:
    import yfinance as yf  # type: ignore

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
                feat["_as_of"] = str(df["ts"].iloc[idx])
                feat["_forward_return"] = float(fwd_ret)
                feat["_benchmark_return"] = 0.0
                feat["_excess_return"] = float(fwd_ret)
                all_rows.append(feat)

        except Exception as exc:
            logger.warning("Skipping %s during alpha training: %s", symbol, exc)

    return all_rows


def _temporal_splits(row_count: int, n_splits: int = 5, embargo: int = 5) -> list[tuple[np.ndarray, np.ndarray]]:
    if row_count < 100:
        return []
    fold_count = min(n_splits, max(2, row_count // 100))
    fold_size = row_count // (fold_count + 1)
    splits = []
    for fold in range(1, fold_count + 1):
        val_start = fold * fold_size
        val_end = row_count if fold == fold_count else min(row_count, val_start + fold_size)
        train_end = max(0, val_start - embargo)
        if train_end <= 0 or val_end <= val_start:
            continue
        splits.append((np.arange(0, train_end), np.arange(val_start, val_end)))
    return splits


def _fit_lightgbm(all_rows: list[dict], *, source: str, metadata: dict) -> None:
    global _model, _feature_names, _model_ready, _model_metrics

    import lightgbm as lgb  # type: ignore
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

    data = pd.DataFrame(all_rows).sort_values("_as_of" if all_rows and "_as_of" in all_rows[0] else "_symbol")
    feature_cols = [c for c in data.columns if not c.startswith("_")]
    x_vals = data[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_vals = data["_label"].astype(int)

    auc_scores = []
    log_losses = []
    brier_scores = []
    splits = _temporal_splits(len(x_vals), n_splits=5, embargo=int(metadata.get("forward_days") or 5))

    for train_idx, val_idx in splits:
        x_train, x_val = x_vals.iloc[train_idx], x_vals.iloc[val_idx]
        y_train, y_val = y_vals.iloc[train_idx], y_vals.iloc[val_idx]
        if len(np.unique(y_train)) < 2 or len(np.unique(y_val)) < 2:
            continue

        clf = lgb.LGBMClassifier(
            n_estimators=250,
            learning_rate=0.035,
            max_depth=4,
            num_leaves=15,
            min_child_samples=30,
            subsample=0.78,
            colsample_bytree=0.78,
            reg_alpha=0.2,
            reg_lambda=0.25,
            random_state=42,
            verbose=-1,
        )
        clf.fit(x_train, y_train)
        prob = np.clip(clf.predict_proba(x_val)[:, 1], 1e-6, 1.0 - 1e-6)
        auc_scores.append(roc_auc_score(y_val, prob))
        log_losses.append(log_loss(y_val, prob))
        brier_scores.append(brier_score_loss(y_val, prob))

    final_model = lgb.LGBMClassifier(
        n_estimators=350,
        learning_rate=0.035,
        max_depth=4,
        num_leaves=15,
        min_child_samples=30,
        subsample=0.78,
        colsample_bytree=0.78,
        reg_alpha=0.2,
        reg_lambda=0.25,
        random_state=42,
        verbose=-1,
    )
    final_model.fit(x_vals, y_vals)

    metrics = {
        "source": source,
        "samples": int(len(all_rows)),
        "features": int(len(feature_cols)),
        "symbols": sorted([str(s) for s in data["_symbol"].dropna().unique().tolist()]) if "_symbol" in data else [],
        "positive_rate": float(y_vals.mean()) if len(y_vals) else 0.0,
        "auc": float(np.mean(auc_scores)) if auc_scores else None,
        "log_loss": float(np.mean(log_losses)) if log_losses else None,
        "brier": float(np.mean(brier_scores)) if brier_scores else None,
        "validation_folds": len(auc_scores),
        **metadata,
    }

    with _model_lock:
        _model = final_model
        _feature_names = feature_cols
        _model_metrics = metrics
        _model_ready = True

    if joblib is not None:
        joblib.dump(final_model, MODEL_PATH)
        joblib.dump(feature_cols, FEATURE_NAMES_PATH)
        METADATA_PATH.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")

    logger.info(
        "Alpha model ready; source=%s features=%s samples=%s auc=%s folds=%s persisted=%s",
        source,
        len(feature_cols),
        len(all_rows),
        metrics.get("auc"),
        metrics.get("validation_folds"),
        bool(joblib is not None),
    )


def _train_model() -> None:
    """
    Train LightGBM on app-owned warehouse bars first, then fall back to Yahoo
    only when the warehouse does not yet contain enough labeled samples.
    """
    global _training

    try:
        logger.info("Training LightGBM alpha model")

        dataset = load_warehouse_training_dataset()
        all_rows = dataset.rows
        source = dataset.source
        metadata = {
            "forward_days": dataset.forward_days,
            "benchmark_symbol": dataset.benchmark_symbol,
        }

        if len(all_rows) < 200:
            logger.warning("Warehouse training data is thin (%s rows); using yfinance fallback", len(all_rows))
            all_rows = _legacy_yfinance_rows()
            source = "yfinance_fallback"
            metadata = {"forward_days": 5, "benchmark_symbol": None}

        if len(all_rows) < 200:
            logger.warning("Not enough training data for alpha model; staying neutral")
            return

        _fit_lightgbm(all_rows, source=source, metadata=metadata)
    except Exception as exc:
        logger.warning("LightGBM training failed; alpha remains neutral: %s", exc)
    finally:
        _training = False


def _load_or_train() -> None:
    global _model, _feature_names, _model_ready, _training, _model_metrics

    if joblib is not None and MODEL_PATH.exists() and FEATURE_NAMES_PATH.exists():
        try:
            with _model_lock:
                _model = joblib.load(MODEL_PATH)
                _feature_names = joblib.load(FEATURE_NAMES_PATH)
                if METADATA_PATH.exists():
                    _model_metrics = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
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

        return probability_to_alpha(prob_up)
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
        "metrics": dict(_model_metrics or {}),
    }
