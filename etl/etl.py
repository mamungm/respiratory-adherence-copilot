"""
ETL pipeline: loads simulated device usage logs into SQLite and engineers
adherence features per patient.

Run after data-generator/generate_data.py has produced:
    data/patients.csv
    data/device_logs.csv

Usage:
    python etl/etl.py
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PATIENTS_CSV = ROOT / "data" / "patients.csv"
EVENTS_CSV = ROOT / "data" / "device_logs.csv"
SCHEMA_SQL = ROOT / "db" / "schema.sql"
DB_PATH = ROOT / "data" / "adherence.db"


def load_raw(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    patients = pd.read_csv(PATIENTS_CSV)
    events = pd.read_csv(EVENTS_CSV)
    patients.to_sql("patients", conn, if_exists="replace", index=False)
    events.to_sql("dose_events", conn, if_exists="replace", index=False)
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
                "computed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return pd.DataFrame(rows)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL.read_text())

    patients, events = load_raw(conn)
    features = engineer_features(patients, events)
    features.to_sql("patient_features", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print(f"Loaded {len(patients)} patients, {len(events)} dose events.")
    print(f"Wrote features for {len(features)} patients to {DB_PATH}")


if __name__ == "__main__":
    main()
