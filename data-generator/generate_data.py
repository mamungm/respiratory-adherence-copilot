"""
Simulated respiratory device usage log generator.

Stands in for real device telemetry (AeroChamber / Aerobika / AeroEclipse)
since we don't have access to Trudell's actual data. Produces two files:

    data/patients.csv      - one row per patient, prescribed dosing + monitoring window
    data/device_logs.csv   - one row per dose event actually taken

Missed doses are represented implicitly: a prescribed slot with no matching
event row. The ETL step reconstructs adherence from that gap.

Usage:
    python data-generator/generate_data.py
"""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

DEVICES = ["AeroChamber", "Aerobika", "AeroEclipse"]
NUM_PATIENTS = 12
MONITORING_DAYS = 60
DOSES_PER_DAY = 2  # prescribed

ROOT = Path(__file__).resolve().parent.parent
PATIENTS_PATH = ROOT / "data" / "patients.csv"
EVENTS_PATH = ROOT / "data" / "device_logs.csv"


def make_patient_profile(patient_id: int, start_date: datetime) -> dict:
    """Each simulated patient gets an adherence tendency and a technique-error tendency,
    drawn from a mix of adherent / at-risk / non-adherent archetypes."""
    adherence_rate = random.choice(
        [
            random.uniform(0.85, 0.98),  # adherent
            random.uniform(0.85, 0.98),
            random.uniform(0.4, 0.7),  # at-risk
            random.uniform(0.15, 0.4),  # non-adherent
        ]
    )
    error_rate = (
        random.uniform(0.0, 0.05) if adherence_rate > 0.8 else random.uniform(0.1, 0.35)
    )
    return {
        "patient_id": f"P{patient_id:03d}",
        "device_type": random.choice(DEVICES),
        "prescribed_doses_per_day": DOSES_PER_DAY,
        "monitoring_start": start_date.date().isoformat(),
        "monitoring_days": MONITORING_DAYS,
        "adherence_rate": adherence_rate,
        "error_rate": error_rate,
    }


def generate_events(profile: dict, start_date: datetime) -> list[dict]:
    events = []
    for day in range(profile["monitoring_days"]):
        date = start_date + timedelta(days=day)
        for dose_num in range(profile["prescribed_doses_per_day"]):
            expected_time = date + timedelta(hours=8 + dose_num * 10)
            taken = random.random() < profile["adherence_rate"]
            if not taken:
                continue  # missed dose -> no row, reconstructed later in ETL

            jitter_std = 45 if profile["adherence_rate"] < 0.7 else 15
            actual_time = expected_time + timedelta(minutes=random.gauss(0, jitter_std))
            technique_error = 1 if random.random() < profile["error_rate"] else 0

            events.append(
                {
                    "patient_id": profile["patient_id"],
                    "device_type": profile["device_type"],
                    "expected_time": expected_time.isoformat(),
                    "event_timestamp": actual_time.isoformat(),
                    "dose_completed": 1,
                    "technique_error": technique_error,
                }
            )
    return events


def main():
    start_date = datetime(2026, 5, 1)
    patients, events = [], []

    for i in range(1, NUM_PATIENTS + 1):
        profile = make_patient_profile(i, start_date)
        patients.append(
            {k: profile[k] for k in (
                "patient_id", "device_type", "prescribed_doses_per_day",
                "monitoring_start", "monitoring_days",
            )}
        )
        events.extend(generate_events(profile, start_date))

    PATIENTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with PATIENTS_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(patients[0].keys()))
        writer.writeheader()
        writer.writerows(patients)

    with EVENTS_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(events[0].keys()))
        writer.writeheader()
        writer.writerows(events)

    print(f"Wrote {len(patients)} patients to {PATIENTS_PATH}")
    print(f"Wrote {len(events)} dose events to {EVENTS_PATH}")


if __name__ == "__main__":
    main()
