# Respiratory Device Adherence Copilot (MVP)

An AI tool that ingests simulated respiratory-device usage data (standing in
for AeroChamber / Aerobika / AeroEclipse telemetry), scores patient adherence
risk, and lets a clinician ask natural-language questions over the data via
an LLM chat layer. Built as a portfolio project targeting Trudell Medical's
AI Engineer role — see `docs/architecture.md` for the full design.

## Stack

- **Data generation & ETL**: Python, pandas
- **Risk scoring**: Python (heuristic model, swappable for a trained classifier)
- **Backend**: Node.js, Express, better-sqlite3, `@anthropic-ai/sdk`
- **Frontend**: React, Vite
- **Storage**: SQLite locally (swap for Postgres/RDS in production)
- **CI/CD**: GitHub Actions

## Quickstart

### 1. Generate data and run the pipeline

```bash
cd respiratory-adherence-copilot
pip install -r etl/requirements.txt -r ml/requirements.txt
python data-generator/generate_data.py   # writes data/patients.csv, data/device_logs.csv
python etl/etl.py                        # writes data/adherence.db + patient_features
python ml/adherence_model.py             # writes adherence_scores, prints a risk table
```

### 2. Start the backend

```bash
cd backend
cp .env.example .env        # add your ANTHROPIC_API_KEY
npm install
npm run dev                 # http://localhost:4000
```

### 3. Start the frontend

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
├── data-generator/   # simulated device log generator (Python)
├── db/               # SQLite schema
├── etl/              # cleaning + feature engineering (Python, pandas)
├── ml/               # heuristic adherence risk scoring (Python)
├── backend/          # Node/Express API + Claude tool-use chat endpoint
├── frontend/         # React + Vite dashboard and chat UI
├── docs/             # architecture notes
└── .github/workflows/ci.yml
```

## Notes

- Data is synthetic (seeded, reproducible) — there is no real patient data here.
- The adherence risk model is a transparent weighted heuristic, not a trained
  model, intentionally kept simple and explainable for an MVP.
- The chat endpoint restricts the LLM to read-only `SELECT` queries against a
  fixed set of tables (see `backend/src/tools/sqlTool.js`) — it cannot write
  to the database.
- Swap SQLite for Postgres/RDS by changing `db.js`/`etl.py` connection setup;
  the schema in `db/schema.sql` was written to be portable between the two.
