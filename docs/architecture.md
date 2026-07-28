# Architecture

Six layers, top to bottom:

**Frontend** — React dashboard + chat widget (Vite dev server, proxies `/api` to the backend).

**Backend API** — Node/Express, the single entry point the frontend and CI/CD deploy target hit.

**Intelligence layer** (three collaborating pieces, all reachable from the chat endpoint):
- Adherence Model (Python, scikit-learn) — a Logistic Regression / Random Forest trained in `ml/train/train_classifier.py` on a simulated 3,000-patient cohort (`ml/train/simulate_training_cohort.py`), since no real outcomes data is available yet. `ml/adherence_model.py` loads the saved model (`ml/model/adherence_risk_model.joblib`) if present and scores patients from `predict_proba`; if no trained model has been produced yet, it falls back to the original weighted heuristic over the same four features, so scoring never breaks.
- SQL Tool (`query_adherence_db`) — Claude writes a restricted, read-only SELECT against `patients`/`dose_events`/`patient_features`/`adherence_scores` for questions about specific patients or the cohort.
- RAG Doc Search Tool (`search_device_docs`) — device IFUs and clinical inhaler-technique guidance (`rag/docs/*.md`, synthetic content, not real Trudell documentation), chunked and embedded with `@xenova/transformers` (`all-MiniLM-L6-v2`, local, no external embeddings API) into a `document_chunks` table via `pgvector`. Query-time search embeds the question with the exact same embedding function used at ingestion time (`backend/src/rag/embeddings.js`) and does a cosine-similarity lookup, so retrieval quality isn't at the mercy of two separate embedding implementations drifting apart. `backend/scripts/ingest_docs.js` handles chunking + loading; re-run it any time the docs change.

Claude decides per-question which tool(s) to call — `backend/src/services/chatService.js` dispatches every `tool_use` block in a turn (not just the first, which the original single-tool implementation assumed), so a question like "why is patient P007 high risk and what should we do" can pull structured risk data and grounded clinical guidance in the same turn.

**Storage** — PostgreSQL + pgvector (`pgvector/pgvector:pg16`, not plain `postgres:16`). Locally via Docker (`docker-compose.yml`), Amazon RDS for Postgres in production (RDS supports the pgvector extension) — same schema, same code, just a different `DATABASE_URL`. Five tables: `patients`, `dose_events`, `patient_features`, `adherence_scores` (real foreign keys, `ON DELETE CASCADE`, so re-running the ETL is idempotent), and `document_chunks` for RAG. `postgres` mounts `db/schema.sql` into `/docker-entrypoint-initdb.d/`, which the official image auto-runs the first time it initializes an empty data directory — no separate migration container needed; `schema.sql`'s `IF NOT EXISTS` clauses make repeated application harmless if you do reapply it manually.

**ETL pipeline** — Python (pandas + SQLAlchemy + psycopg2) job that cleans raw dose-event logs and engineers adherence features: adherence rate, longest missed-dose streak, dose-interval variance, technique-error rate.

**Data source** — simulated device usage logs (`data-generator/generate_data.py`), standing in for real AeroChamber / Aerobika / AeroEclipse telemetry.

CI (`.github/workflows/ci.yml`) spins up a real Postgres service container and runs the Python pipeline end-to-end against it, then installs/builds both the backend and frontend on every push — the DevOps/CI-CD piece called out in the JD. In production this would deploy the backend to AWS Lambda/ECS, the frontend to S3+CloudFront, and the database to RDS.

## Data flow

1. `data-generator/generate_data.py` → `data/patients.csv`, `data/device_logs.csv`
2. `etl/etl.py` → applies `db/schema.sql`, truncates + reloads Postgres from the CSVs, computes `patient_features`
3. (optional, one-time) `ml/train/simulate_training_cohort.py` → `ml/train/training_data.csv`, then `ml/train/train_classifier.py` → `ml/model/adherence_risk_model.joblib` + `ml/model/model_metadata.json`
4. `ml/adherence_model.py` → reads `patient_features`, scores with the trained model if step 3 has been run (heuristic otherwise), writes `adherence_scores`
5. (optional) `backend/scripts/ingest_docs.js` → chunks + embeds `rag/docs/*.md`, writes `document_chunks`
6. `backend` → serves `/api/patients` (reads from Postgres via a connection pool) and `/api/chat` (Claude + SQL tool + RAG doc search tool)
7. `frontend` → dashboard table + chat widget calling the backend

## Why Postgres over SQLite

The MVP originally used SQLite for zero-setup local dev. Swapping to Postgres (via `docker-compose up` locally, RDS in production) better matches the JD's "SQL databases" and AWS/cloud-services requirements, and makes the local/dev/prod story a straight line: same schema, same queries, same connection code — only `DATABASE_URL` changes.
