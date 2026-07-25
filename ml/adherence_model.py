"""
Adherence risk scoring.

Two scoring paths, chosen automatically:

1. Trained classifier (ml/model/adherence_risk_model.joblib) -- a Logistic
   Regression or Random Forest trained in ml/train/train_classifier.py on a
   larger simulated cohort (ml/train/simulate_training_cohort.py). Used
   whenever the model artifact is present.
2. Heuristic fallback -- the original transparent weighted formula over the
   same four features, used only if no trained model exists yet. Kept
   deliberately, both as a sanity check against the trained model and as a
   simple, explainable baseline a clinician can validate by eye.

To train the classifier (optional, but the "real" scoring path):
    python ml/train/simulate_training_cohort.py
    python ml/train/train_classifier.py

Then just run this script as usual -- it will pick up the trained model:
    python ml/adherence_model.py

Connects to the same PostgreSQL database as etl/etl.py (DATABASE_URL or
discrete PG* env vars, see etl/etl.py for details).
"""
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
import sqlalchemy as sa
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MODEL_PATH = ROOT / "ml" / "model" / "adherence_risk_model.joblib"

FEATURES = [
    "adherence_rate",
    "missed_dose_max_streak",
    "dose_interval_variance",
    "technique_error_rate",
]

# --- heuristic fallback config ---
HEURISTIC_WEIGHTS = {
    "missed_adherence": 0.50,   # 1 - adherence_rate
    "missed_streak": 0.25,      # normalized missed_dose_max_streak
    "interval_variance": 0.10,  # normalized dose_interval_variance
    "technique_error_rate": 0.15,
}
STREAK_NORM_DAYS = 14       # 14+ consecutive missed days -> max contribution
VARIANCE_NORM_MIN2 = 5000   # variance ceiling (minutes^2) for normalization


def get_engine() -> sa.Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        host = os.environ.get("PGHOST", "localhost")
        port = os.environ.get("PGPORT", "5432")
        name = os.environ.get("PGDATABASE", "adherence")
        user = os.environ.get("PGUSER", "postgres")
        password = os.environ.get("PGPASSWORD", "postgres")
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return sa.create_engine(url)


def risk_tier(score: float) -> str:
    if score >= 66:
        return "High"
    if score >= 33:
        return "Medium"
    return "Low"


def heuristic_score(f: pd.Series) -> float:
    missed_adherence = 1 - f["adherence_rate"]
    missed_streak_norm = min(f["missed_dose_max_streak"] / STREAK_NORM_DAYS, 1.0)
    variance_norm = min(f["dose_interval_variance"] / VARIANCE_NORM_MIN2, 1.0)
    error_rate = f["technique_error_rate"]

    raw_score = (
        HEURISTIC_WEIGHTS["missed_adherence"] * missed_adherence
        + HEURISTIC_WEIGHTS["missed_streak"] * missed_streak_norm
        + HEURISTIC_WEIGHTS["interval_variance"] * variance_norm
        + HEURISTIC_WEIGHTS["technique_error_rate"] * error_rate
    )
    return round(raw_score * 100, 1)


def score_with_heuristic(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, f in features.iterrows():
        score = heuristic_score(f)
        rows.append(
            {
                "patient_id": f["patient_id"],
                "risk_score": score,
                "risk_tier": risk_tier(score),
                "scored_at": datetime.now(timezone.utc),
            }
        )
    return pd.DataFrame(rows)


def score_with_model(features: pd.DataFrame, model) -> pd.DataFrame:
    proba = model.predict_proba(features[FEATURES])[:, 1]
    rows = []
    for pid, p in zip(features["patient_id"], proba):
        score = round(float(p) * 100, 1)
        rows.append(
            {
                "patient_id": pid,
                "risk_score": score,
                "risk_tier": risk_tier(score),
                "scored_at": datetime.now(timezone.utc),
            }
        )
    return pd.DataFrame(rows)


def main():
    engine = get_engine()
    features = pd.read_sql("SELECT * FROM patient_features", engine)

    if MODEL_PATH.exists():
        model = joblib.load(MODEL_PATH)
        print(f"Using trained classifier: {MODEL_PATH.relative_to(ROOT)}")
        scores = score_with_model(features, model)
    else:
        print(
            "No trained model found at ml/model/ -- using heuristic fallback.\n"
            "Run `python ml/train/simulate_training_cohort.py` then "
            "`python ml/train/train_classifier.py` to train one."
        )
        scores = score_with_heuristic(features)

    with engine.begin() as conn:
        conn.exec_driver_sql("TRUNCATE TABLE adherence_scores")
    scores.to_sql("adherence_scores", engine, if_exists="append", index=False)

    print(scores.sort_values("risk_score", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
