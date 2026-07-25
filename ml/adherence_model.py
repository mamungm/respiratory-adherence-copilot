"""
Adherence risk scoring.

MVP heuristic model: a weighted formula over the engineered features in
patient_features. This is intentionally simple and explainable so it can
be validated by a clinician before any real ML is introduced. Swap this
out for a trained classifier once labeled outcome data (e.g. exacerbation
events, hospital readmission) is available.

Connects to the same PostgreSQL database as etl/etl.py (DATABASE_URL or
discrete PG* env vars, see etl/etl.py for details).

Usage:
    python ml/adherence_model.py
"""
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

WEIGHTS = {
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


def score_patients(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, f in features.iterrows():
        missed_adherence = 1 - f["adherence_rate"]
        missed_streak_norm = min(f["missed_dose_max_streak"] / STREAK_NORM_DAYS, 1.0)
        variance_norm = min(f["dose_interval_variance"] / VARIANCE_NORM_MIN2, 1.0)
        error_rate = f["technique_error_rate"]

        raw_score = (
            WEIGHTS["missed_adherence"] * missed_adherence
            + WEIGHTS["missed_streak"] * missed_streak_norm
            + WEIGHTS["interval_variance"] * variance_norm
            + WEIGHTS["technique_error_rate"] * error_rate
        )
        score = round(raw_score * 100, 1)

        rows.append(
            {
                "patient_id": f["patient_id"],
                "risk_score": score,
                "risk_tier": risk_tier(score),
                "scored_at": datetime.now(timezone.utc),
            }
        )
    return pd.DataFrame(rows)


def main():
    engine = get_engine()
    features = pd.read_sql("SELECT * FROM patient_features", engine)
    scores = score_patients(features)

    with engine.begin() as conn:
        conn.exec_driver_sql("TRUNCATE TABLE adherence_scores")
    scores.to_sql("adherence_scores", engine, if_exists="append", index=False)

    print(scores.sort_values("risk_score", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
