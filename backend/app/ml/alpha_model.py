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

import threading
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

from app.ml.features import build_features

MODEL_PATH = Path(__file__).parent / "lgbm_alpha.pkl"
FEATURE_NAMES_PATH = Path(__file__).parent / "feature_names.pkl"

_model = None
_feature_names = None
_model_lock = threading.Lock()
_model_ready = False
_training = False


def _train_model():
    """
    Train LightGBM on historical data for the watchlist.
    Uses TimeSeriesSplit to avoid lookahead bias.
    Saves model to disk.
    """
    global _model, _feature_names, _model_ready, _training

    try:
        import lightgbm as lgb
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import roc_auc_score
        import yfinance as yf

        print("🤖 Training LightGBM alpha model...")

        WATCHLIST = ["AAPL", "MSFT", "NVDA", "SPY", "TSLA", "AMZN", "GOOGL", "META", "JPM", "GS"]
        FORWARD_DAYS = 5
        all_rows = []

        for sym in WATCHLIST:
            try:
                ticker = yf.Ticker(sym)
                df = ticker.history(period="2y", interval="1d")
                if df.empty or len(df) < 100:
                    continue

                df = df.reset_index()
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                df = df.rename(columns={
                    "Date": "ts", "Open": "open", "High": "high",
                    "Low": "low", "Close": "close", "Volume": "volume",
                })

                for i in range(60, len(df) - FORWARD_DAYS):
                    window = df.iloc[:i+1].copy()
                    feat = build_features(window)
                    if not feat:
                        continue

                    fwd_ret = (df["close"].iloc[i + FORWARD_DAYS] - df["close"].iloc[i]) / (df["close"].iloc[i] + 1e-9)
                    feat["_label"] = int(fwd_ret > 0.0)
                    feat["_symbol"] = sym
                    all_rows.append(feat)

            except Exception as e:
                print(f"  ⚠️ Skipping {sym}: {e}")
                continue

        if len(all_rows) < 200:
            print("⚠️ Not enough training data — alpha will be neutral until more data exists")
            return

        data = pd.DataFrame(all_rows)
        feature_cols = [c for c in data.columns if not c.startswith("_")]
        X = data[feature_cols].fillna(0.0)
        y = data["_label"]

        tscv = TimeSeriesSplit(n_splits=5)
        auc_scores = []

        for train_idx, val_idx in tscv.split(X):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

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
            clf.fit(X_tr, y_tr)
            prob = clf.predict_proba(X_val)[:, 1]
            if len(np.unique(y_val)) > 1:
                auc_scores.append(roc_auc_score(y_val, prob))

        avg_auc = np.mean(auc_scores) if auc_scores else 0.5
        print(f"  📊 Cross-val AUC: {avg_auc:.4f} ({len(auc_scores)} folds)")

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
        final_model.fit(X, y)

        with _model_lock:
            _model = final_model
            _feature_names = feature_cols
            _model_ready = True

        joblib.dump(final_model, MODEL_PATH)
        joblib.dump(feature_cols, FEATURE_NAMES_PATH)
        print(f"✅ LightGBM alpha model trained — {len(feature_cols)} features, {len(all_rows)} samples, AUC={avg_auc:.4f}")

    except Exception as e:
        print(f"⚠️ LightGBM training failed: {e}")
    finally:
        _training = False


def _load_or_train():
    global _model, _feature_names, _model_ready, _training

    if MODEL_PATH.exists() and FEATURE_NAMES_PATH.exists():
        try:
            with _model_lock:
                _model = joblib.load(MODEL_PATH)
                _feature_names = joblib.load(FEATURE_NAMES_PATH)
                _model_ready = True
            print("✅ LightGBM alpha model loaded from disk")
            return
        except Exception as e:
            print(f"⚠️ Failed to load saved model: {e} — retraining")

    _training = True
    t = threading.Thread(target=_train_model, daemon=True, name="lgbm-trainer")
    t.start()


def ensure_model():
    global _training
    if not _model_ready and not _training:
        _training = True
        _load_or_train()


def predict(df: pd.DataFrame) -> float:
    """
    Given OHLCV DataFrame, return alpha signal in [-1, 1].
    Returns 0.0 if model not ready yet.
    """
    if not _model_ready or _model is None:
        return 0.0

    # Accept either `ts` or `date` — training used `ts`.
    if "ts" not in df.columns and "date" in df.columns:
        df = df.rename(columns={"date": "ts"})

    feat = build_features(df)
    if not feat:
        return 0.0

    try:
        with _model_lock:
            # ✅ CRITICAL FIX:
            # Use reindex(columns=...) to avoid KeyError / schema drift when features change.
            X = pd.DataFrame([feat]).reindex(columns=_feature_names, fill_value=0.0)
            prob_up = float(_model.predict_proba(X)[0][1])

        score = (prob_up - 0.5) * 2.0
        return float(np.clip(score, -1.0, 1.0))

    except Exception as e:
        print(f"⚠️ Alpha prediction failed: {e}")
        return 0.0


def model_status() -> dict:
    return {
        "ready": _model_ready,
        "training": _training,
        "features": len(_feature_names) if _feature_names else 0,
        "path": str(MODEL_PATH) if MODEL_PATH.exists() else None,
    }