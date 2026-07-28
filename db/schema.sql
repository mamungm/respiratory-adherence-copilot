-- Schema for the Respiratory Device Adherence Copilot MVP (PostgreSQL).
-- Run locally via docker-compose (see ../docker-compose.yml) or against
-- Amazon RDS for Postgres in production.

-- Requires the pgvector extension (image is pgvector/pgvector:pg16, not
-- plain postgres:16 - see docker-compose.yml / k8s/postgres.yaml).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS patients (
    patient_id                  TEXT PRIMARY KEY,
    device_type                 TEXT NOT NULL,
    prescribed_doses_per_day    INTEGER NOT NULL,
    monitoring_start            DATE NOT NULL,
    monitoring_days             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dose_events (
    id                  SERIAL PRIMARY KEY,
    patient_id          TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    device_type         TEXT NOT NULL,
    expected_time       TIMESTAMP NOT NULL,
    event_timestamp     TIMESTAMP NOT NULL,
    dose_completed      INTEGER NOT NULL,
    technique_error     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_features (
    patient_id              TEXT PRIMARY KEY REFERENCES patients(patient_id) ON DELETE CASCADE,
    adherence_rate          REAL NOT NULL,
    missed_dose_max_streak  INTEGER NOT NULL,
    dose_interval_variance  REAL NOT NULL,
    technique_error_rate    REAL NOT NULL,
    computed_at             TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS adherence_scores (
    patient_id      TEXT PRIMARY KEY REFERENCES patients(patient_id) ON DELETE CASCADE,
    risk_score      REAL NOT NULL,
    risk_tier       TEXT NOT NULL,
    scored_at       TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dose_events_patient_id ON dose_events(patient_id);

-- RAG corpus: device IFUs + clinical guidance, chunked and embedded by
-- backend/scripts/ingest_docs.js. 384 dims = all-MiniLM-L6-v2 output size
-- (see backend/src/rag/embeddings.js). No ANN index yet - a sequential
-- scan over a few hundred chunks is plenty fast; add an ivfflat/hnsw index
-- here once the corpus is large enough to need one.
CREATE TABLE IF NOT EXISTS document_chunks (
    id            SERIAL PRIMARY KEY,
    source        TEXT NOT NULL,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    embedding     VECTOR(384) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
