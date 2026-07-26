# Respiratory Device Adherence Copilot (MVP)

An AI tool that ingests simulated respiratory-device usage data (standing in
for AeroChamber / Aerobika / AeroEclipse telemetry), scores patient adherence
risk, and lets a clinician ask natural-language questions over the data via
an LLM chat layer. Built as a portfolio project targeting Trudell Medical's
AI Engineer role — see `docs/architecture.md` for the full design.

## Stack

- **Data generation & ETL**: Python, pandas, SQLAlchemy, psycopg2
- **Risk scoring**: Python, scikit-learn — trained classifier (Logistic Regression / Random Forest, whichever wins on ROC-AUC), with an explainable heuristic as an automatic fallback
- **Backend**: Node.js, Express, `pg` (node-postgres), `@anthropic-ai/sdk`
- **Frontend**: React, Vite
- **Storage**: PostgreSQL (Docker locally, Amazon RDS in production)
- **CI/CD**: GitHub Actions (runs a real Postgres service container)

## Quickstart

### 1. Start Postgres (and optionally the backend + frontend)

```bash
cd respiratory-adherence-copilot
docker compose up -d postgres          # starts Postgres on localhost:5432
# or: docker compose up -d --build      # also builds + runs backend (:4000) and frontend (:5173)
```

A `migrate` service applies `db/schema.sql` to Postgres automatically on
every `docker compose up` (it's a one-off container gated on Postgres's
healthcheck; `backend` waits for it to exit successfully before starting).
`schema.sql` uses `CREATE TABLE/INDEX IF NOT EXISTS`, so re-running it
against an already-migrated database is a safe no-op. `backend` builds from
`backend/Dockerfile` and reads `backend/.env` for `ANTHROPIC_API_KEY` (make
sure that file exists and has a real key before using `--build`). `frontend`
builds a static Vite bundle served by nginx, which proxies `/api/*` to the
`backend` container the same way the Vite dev server proxy does for
`npm run dev`. If you'd rather run with hot-reload during development, just
start `postgres` alone as shown above and skip to steps 4-5 (the ETL step
below also applies the schema, so you don't need `migrate` if you're not
using the Docker backend/frontend).

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

### 3. Train the risk classifier (optional, but this is the "real" scoring path)

```bash
python ml/train/simulate_training_cohort.py   # 3,000-patient synthetic cohort + simulated outcome label
python ml/train/train_classifier.py           # trains + evaluates Logistic Regression and Random Forest,
                                                # saves the better one to ml/model/
python ml/adherence_model.py                  # re-run scoring - now uses the trained model automatically
```

There's no real outcomes data (e.g. hospital readmission, exacerbation
events) available for this project, so `simulate_training_cohort.py`
generates a much larger synthetic population than the 12-patient demo
dashboard and derives a binary "adverse event" label from the same four
features via a logistic function plus noise — learnable, not perfectly
separable, similar to what a real adherence → outcome relationship would
look like. Swap in real labeled data later and `train_classifier.py` itself
doesn't need to change.

If you skip this step, `ml/adherence_model.py` automatically falls back to
the original weighted heuristic — nothing breaks, it just scores less
precisely.

### 4. Start the backend

```bash
cd backend
cp .env.example .env        # add your ANTHROPIC_API_KEY (DATABASE_URL already points at docker-compose)
npm install
npm run dev                 # http://localhost:4000
```

### 5. Start the frontend

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
├── ml/                # trained classifier + heuristic fallback for risk scoring
│   └── train/          # synthetic training cohort + train/eval script
├── backend/           # Node/Express API + Claude tool-use chat endpoint (pg pool)
├── frontend/          # React + Vite dashboard and chat UI (nginx + proxy in Docker)
├── docs/              # architecture notes
└── .github/workflows/ci.yml
```

## Notes

- Data is synthetic (seeded, reproducible) — there is no real patient data here.
- Risk scoring has two paths: a trained classifier (`ml/model/`, gitignored,
  regenerate with the two commands above) used automatically when present,
  and a transparent weighted heuristic used as a fallback and as a sanity
  check against the trained model's predictions.
- The chat endpoint restricts the LLM to read-only, single-statement `SELECT`
  queries against a fixed set of tables (see `backend/src/tools/sqlTool.js`) —
  it cannot write to the database.
- `etl/etl.py` is idempotent: it applies `db/schema.sql`, truncates existing
  rows (`ON DELETE CASCADE` from `patients`), and reloads from the CSVs, so
  re-running it is safe.
- Swapping environments (local Docker → RDS → any other Postgres) is a
  `DATABASE_URL` change only, no code changes.
