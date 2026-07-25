# Architecture

Six layers, top to bottom:

**Frontend** — React dashboard + chat widget (Vite dev server, proxies `/api` to the backend).

**Backend API** — Node/Express, the single entry point the frontend and CI/CD deploy target hit.

**Intelligence layer** (two parallel services):
- Adherence Model (Python) — scores risk from engineered features.
- LLM Query Layer (Claude API via `@anthropic-ai/sdk`) — translates natural-language questions into SQL through a restricted `query_adherence_db` tool and summarizes results.

**Storage** — SQLite locally (`data/adherence.db`) standing in for Postgres/RDS in production. Four tables: `patients`, `dose_events`, `patient_features`, `adherence_scores`.

**ETL pipeline** — Python (pandas) job that cleans raw dose-event logs and engineers adherence features: adherence rate, longest missed-dose streak, dose-interval variance, technique-error rate.

**Data source** — simulated device usage logs (`data-generator/generate_data.py`), standing in for real AeroChamber / Aerobika / AeroEclipse telemetry.

CI (`.github/workflows/ci.yml`) runs the Python pipeline end-to-end and installs/builds both the backend and frontend on every push — the DevOps/CI-CD piece called out in the JD. In production this would deploy the backend to AWS Lambda/ECS, the frontend to S3+CloudFront, and the database to RDS.

## Data flow

1. `data-generator/generate_data.py` → `data/patients.csv`, `data/device_logs.csv`
2. `etl/etl.py` → loads CSVs into `data/adherence.db`, computes `patient_features`
3. `ml/adherence_model.py` → reads `patient_features`, writes `adherence_scores`
4. `backend` → serves `/api/patients` (reads from SQLite) and `/api/chat` (Claude + SQL tool)
5. `frontend` → dashboard table + chat widget calling the backend
