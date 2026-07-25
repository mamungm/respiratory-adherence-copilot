# Respiratory Device Adherence Copilot (MVP)

An AI tool that ingests simulated respiratory-device usage data (standing in
for AeroChamber / Aerobika / AeroEclipse telemetry), scores patient adherence
risk, and lets a clinician ask natural-language questions over the data via
an LLM chat layer. Built as a portfolio project targeting Trudell Medical's
AI Engineer role — see `docs/architecture.md` for the full design.

## Stack

- **Data generation & ETL**: Python, pandas, SQLAlchemy, psycopg2
- **Risk scoring**: Python (heuristic model, swappable for a trained classifier)
- **Backend**: Node.js, Express, `pg` (node-postgres), `@anthropic-ai/sdk`
- **Frontend**: React, Vite
- **Storage**: PostgreSQL (Docker locally, Amazon RDS in production)
- **CI/CD**: GitHub Actions (runs a real Postgres service container)

## Quickstart

### 1. Start Postgres

```bash
cd respiratory-adherence-copilot
docker compose up -d          # starts Postgres on localhost:5432
```

### 2. Generate data and run the pipeline

```bash
pip install -r etl/requirements.txt -r ml/requirements.txt
python data-generator/generate_data.py   # writes data/patients.csv, data/device_logs.csv
python etl/etl.py                        # applies schema, loads Postgres, computes patient_features
python ml/adherence_model.py             # writes adherence_scores, prints a risk table
```

By default the scripts connect to `postgresql://postgres:postgres@localhost:5432/adherence`
(matching `docker-compose.yml`). Override with a `DATABASE_URL` env var, or
copy `.env.example` → `.env` in the repo root and set `PGHOST`/`PGUSER`/etc.
there to point at RDS or any other Postgres instance.

### 3. Start the backend

```bash
cd backend
cp .env.example .env        # add your ANTHROPIC_API_KEY (DATABASE_URL already points at docker-compose)
npm install
npm run dev                 # http://localhost:4000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

Open the frontend URL — you'll see the adherence dashboard and a chat widget
that queries the database through Claude.

## Repo layout

```
respiratory-adherence-copilot/
├── docker-compose.yml # local Postgres for development
├── data-generator/    # simulated device log generator (Python)
├── db/                # PostgreSQL schema
├── etl/                # cleaning + feature engineering (Python, pandas + SQLAlchemy)
├── ml/                # heuristic adherence risk scoring (Python)
├── backend/           # Node/Express API + Claude tool-use chat endpoint (pg pool)
├── frontend/          # React + Vite dashboard and chat UI
├── docs/              # architecture notes
└── .github/workflows/ci.yml
```

## Notes

- Data is synthetic (seeded, reproducible) — there is no real patient data here.
- The adherence risk model is a transparent weighted heuristic, not a trained
  model, intentionally kept simple and explainable for an MVP.
- The chat endpoint restricts the LLM to read-only, single-statement `SELECT`
  queries against a fixed set of tables (see `backend/src/tools/sqlTool.js`) —
  it cannot write to the database.
- `etl/etl.py` is idempotent: it applies `db/schema.sql`, truncates existing
  rows (`ON DELETE CASCADE` from `patients`), and reloads from the CSVs, so
  re-running it is safe.
- Swapping environments (local Docker → RDS → any other Postgres) is a
  `DATABASE_URL` change only, no code changes.
