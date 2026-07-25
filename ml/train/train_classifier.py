"""
Trains a classifier that predicts adherence-related risk from the four
engineered features (adherence_rate, missed_dose_max_streak,
dose_interval_variance, technique_error_rate), using the synthetic cohort
from simulate_training_cohort.py.

Trains two candidates -- Logistic Regression (interpretable baseline) and
Random Forest -- evaluates both on a held-out test split, keeps whichever
scores higher on ROC-AUC, and saves it to
ml/model/adherence_risk_model.joblib alongside metadata (metrics, feature
list, feature importance, trained_at) in ml/model/model_metadata.json.

adherence_model.py picks up the saved model automatically if present;
otherwise it falls back to the heuristic scorer.

Usage:
    python ml/train/simulate_training_cohort.py   # if training_data.csv doesn't exist yet
    python ml/train/train_classifier.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent.parent
TRAINING_CSV = Path(__file__).resolve().parent / "training_data.csv"
MODEL_DIR = ROOT / "ml" / "model"
MODEL_PATH = MODEL_DIR / "adherence_risk_model.joblib"
METADATA_PATH = MODEL_DIR / "model_metadata.json"

FEATURES = [
    "adherence_rate",
    "missed_dose_max_streak",
    "dose_interval_variance",
    "technique_error_rate",
]
TARGET = "adverse_event"


def evaluate(name: str, model, X_test, y_test) -> dict:
    proba = model.predict_proba(X_test)[:, 1]
    preds = model.predict(X_test)
    metrics = {
        "model": name,
        "accuracy": round(accuracy_score(y_test, preds), 4),
        "precision": round(precision_score(y_test, preds), 4),
        "recall": round(recall_score(y_test, preds), 4),
        "f1": round(f1_score(y_test, preds), 4),
        "roc_auc": round(roc_auc_score(y_test, proba), 4),
    }
    print(f"{name}: {metrics}")
    return metrics


def main():
    if not TRAINING_CSV.exists():
        raise SystemExit(
            f"{TRAINING_CSV} not found. Run "
            "`python ml/train/simulate_training_cohort.py` first."
        )

    df = pd.read_csv(TRAINING_CSV)
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    candidates = {
        "logistic_regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=6,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=42,
        ),
    }

    results, fitted = [], {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        fitted[name] = model
        results.append(evaluate(name, model, X_test, y_test))

    best = max(results, key=lambda r: r["roc_auc"])
    best_model = fitted[best["model"]]

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, MODEL_PATH)

    if hasattr(best_model, "feature_importances_"):
        importance = dict(zip(FEATURES, best_model.feature_importances_.round(4).tolist()))
    elif hasattr(best_model, "coef_"):
        importance = dict(zip(FEATURES, best_model.coef_[0].round(4).tolist()))
    else:
        importance = None

    metadata = {
        "chosen_model": best["model"],
        "features": FEATURES,
        "target": TARGET,
        "metrics": results,
        "feature_importance": importance,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": len(df),
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2))

    print(f"\nSelected {best['model']} (ROC-AUC {best['roc_auc']}), saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
