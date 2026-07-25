"""
ETL pipeline: loads simulated device usage logs into PostgreSQL and
engineers adherence features per patient.

Run after data-generator/generate_data.py has produced:
    data/patients.csv
    data/device_logs.csv

Connects using DATABASE_URL if set, otherwise falls back to discrete
PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD env vars (defaults match
docker-compose.yml). Copy .env.example to .env in the repo root to
configure locally.

Usage:
    python etl/etl.py
"""
import os
import sqlalchemy as sa
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
PATIENTS_CSV = ROOT / "data" / "patients.csv"
EVENTS_CSV = ROOT / "data" / "device_logs.csv"
SCHEMA_SQL = ROOT / "db" / "schema.sql"

load_dotenv(ROOT / ".env")


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


def apply_schema(engine: sa.Engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA_SQL.read_text())


def reset_tables(engine: sa.Engine):
    """Idempotent re-run: wipe existing rows before reloading from CSVs.
    ON DELETE CASCADE on the foreign keys means truncating patients clears
    everything downstream too."""
    with engine.begin() as conn:
        conn.exec_driver_sql("TRUNCATE TABLE patients RESTART IDENTITY CASCADE")


def load_raw(engine: sa.Engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    patients = pd.read_csv(PATIENTS_CSV)
    events = pd.read_csv(EVENTS_CSV)
    patients.to_sql("patients", engine, if_exists="append", index=False)
    events.to_sql("dose_events", engine, if_exists="append", index=False)
    return patients, events


def engineer_features(patients: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    events["expected_time"] = pd.to_datetime(events["expected_time"])
    events["event_timestamp"] = pd.to_datetime(events["event_timestamp"])
    events["day"] = events["expected_time"].dt.date

    rows = []
    for _, patient in patients.iterrows():
        pid = patient["patient_id"]
        p_events = events[events["patient_id"] == pid]

        expected_doses = patient["prescribed_doses_per_day"] * patient["monitoring_days"]
        taken_doses = len(p_events)
        adherence_rate = taken_doses / expected_doses if expected_doses else 0.0

        # Missed-dose streak: walk every monitored day, count the longest
        # consecutive run of days with zero recorded doses.
        all_days = pd.date_range(
            patient["monitoring_start"], periods=patient["monitoring_days"], freq="D"
        ).date
        days_with_dose = set(p_events["day"])
        streak = max_streak = 0
        for d in all_days:
            if d in days_with_dose:
                streak = 0
            else:
                streak += 1
                max_streak = max(max_streak, streak)

        if len(p_events) > 1:
            deltas_minutes = (
                p_events["event_timestamp"] - p_events["expected_time"]
            ).dt.total_seconds() / 60
            interval_variance = float(np.var(deltas_minutes))
        else:
            interval_variance = 0.0

        technique_error_rate = float(p_events["technique_error"].mean()) if taken_doses else 0.0

        rows.append(
            {
                "patient_id": pid,
                "adherence_rate": round(adherence_rate, 4),
                "missed_dose_max_streak": int(max_streak),
                "dose_interval_variance": round(interval_variance, 2),
                "technique_error_rate": round(technique_error_rate, 4),
                "computed_at": datetime.now(timezone.utc),
            }
        )

    return pd.DataFrame(rows)


def main():
    engine = get_engine()
    apply_schema(engine)
    reset_tables(engine)

    patients, events = load_raw(engine)
    features = engineer_features(patients, events)
    features.to_sql("patient_features", engine, if_exists="append", index=False)

    print(f"Loaded {len(patients)} patients, {len(events)} dose events.")
    print(f"Wrote features for {len(features)} patients to Postgres.")


if __name__ == "__main__":
    main()
