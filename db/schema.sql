-- Schema for the Respiratory Device Adherence Copilot MVP.
-- Written to run on SQLite for local/demo use (zero server setup).
-- Types are kept portable so this can be pointed at Postgres/RDS for
-- production with little to no change.

CREATE TABLE IF NOT EXISTS patients (
    patient_id                  TEXT PRIMARY KEY,
    device_type                 TEXT NOT NULL,
    prescribed_doses_per_day    INTEGER NOT NULL,
    monitoring_start            TEXT NOT NULL,
    monitoring_days             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dose_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id          TEXT NOT NULL REFERENCES patients(patient_id),
    device_type         TEXT NOT NULL,
    expected_time       TEXT NOT NULL,
    event_timestamp     TEXT NOT NULL,
    dose_completed      INTEGER NOT NULL,
    technique_error     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_features (
    patient_id              TEXT PRIMARY KEY REFERENCES patients(patient_id),
    adherence_rate          REAL NOT NULL,
    missed_dose_max_streak  INTEGER NOT NULL,
    dose_interval_variance  REAL NOT NULL,
    technique_error_rate    REAL NOT NULL,
    computed_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS adherence_scores (
    patient_id      TEXT PRIMARY KEY REFERENCES patients(patient_id),
    risk_score      REAL NOT NULL,
    risk_tier       TEXT NOT NULL,
    scored_at       TEXT NOT NULL
);
