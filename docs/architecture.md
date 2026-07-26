# Architecture

Six layers, top to bottom:

**Frontend** — React dashboard + chat widget (Vite dev server, proxies `/api` to the backend).

**Backend API** — Node/Express, the single entry point the frontend and CI/CD deploy target hit.

**Intelligence layer** (two parallel services):
- Adherence Model (Python, scikit-learn) — a Logistic Regression / Random Forest trained in `ml/train/train_classifier.py` on a simulated 3,000-patient cohort (`ml/train/simulate_training_cohort.py`), since no real outcomes data is available yet. `ml/adherence_model.py` loads the saved model (`ml/model/adherence_risk_model.joblib`) if present and scores patients from `predict_proba`; if no trained model has been produced yet, it falls back to the original weighted heuristic over the same four features, so scoring never breaks.
- LLM Query Layer (Claude API via `@anthropic-ai/sdk`) — translates natural-language questions into SQL through a restricted `query_adherence_db` tool and summarizes results.

**Storage** — PostgreSQL. Locally via Docker (`docker-compose.yml`), Amazon RDS for Postgres in production — same schema, same code, just a different `DATABASE_URL`. Four tables: `patients`, `dose_events`, `patient_features`, `adherence_scores`, with real foreign keys and `ON DELETE CASCADE` so re-running the ETL is idempotent. A `migrate` one-off container applies `db/schema.sql` on every `docker compose up` (gated on Postgres's healthcheck, `backend` waits on its successful exit) so the schema always exists even if you never run the Python ETL — `schema.sql`'s `IF NOT EXISTS` clauses make repeated application harmless.

**ETL pipeline** — Python (pandas + SQLAlchemy + psycopg2) job that cleans raw dose-event logs and engineers adherence features: adherence rate, longest missed-dose streak, dose-interval variance, technique-error rate.

**Data source** — simulated device usage logs (`data-generator/generate_data.py`), standing in for real AeroChamber / Aerobika / AeroEclipse telemetry.

CI (`.github/workflows/ci.yml`) spins up a real Postgres service container and runs the Python pipeline end-to-end against it, then installs/builds both the backend and frontend on every push — the DevOps/CI-CD piece called out in the JD. In production this would deploy the backend to AWS Lambda/ECS, the frontend to S3+CloudFront, and the database to RDS.

## Data flow

1. `data-generator/generate_data.py` → `data/patients.csv`, `data/device_logs.csv`
2. `etl/etl.py` → applies `db/schema.sql`, truncates + reloads Postgres from the CSVs, computes `patient_features`
3. (optional, one-time) `ml/train/simulate_training_cohort.py` → `ml/train/training_data.csv`, then `ml/train/train_classifier.py` → `ml/model/adherence_risk_model.joblib` + `ml/model/model_metadata.json`
4. `ml/adherence_model.py` → reads `patient_features`, scores with the trained model if step 3 has been run (heuristic otherwise), writes `adherence_scores`
5. `backend` → serves `/api/patients` (reads from Postgres via a connection pool) and `/api/chat` (Claude + SQL tool)
6. `frontend` → dashboard table + chat widget calling the backend

## Why Postgres over SQLite

The MVP originally used SQLite for zero-setup local dev. Swapping to Postgres (via `docker-compose up` locally, RDS in production) better matches the JD's "SQL databases" and AWS/cloud-services requirements, and makes the local/dev/prod story a straight line: same schema, same queries, same connection code — only `DATABASE_URL` changes.
