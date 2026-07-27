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
- **Deployment**: Docker Compose (local) or Kubernetes (`k8s/`, see below)

## Quickstart

### 1. Start Postgres (and optionally the backend + frontend)

```bash
cd respiratory-adherence-copilot
docker compose up -d postgres          # starts Postgres on localhost:5432
# or: docker compose up -d --build      # also builds + runs backend (:4000) and frontend (:5173)
```

`postgres` mounts `db/schema.sql` into `/docker-entrypoint-initdb.d/`, which
the official Postgres image auto-runs the first time it initializes an
empty data directory — no separate migration step needed. That only fires
once per volume: if you already have a `pgdata` volume from an earlier run
that never got the schema applied, reset it with `docker compose down -v`
before bringing it back up. `backend` builds from `backend/Dockerfile` and
reads `backend/.env` for `ANTHROPIC_API_KEY` (make sure that file exists
and has a real key before using `--build`). `frontend` builds a static Vite
bundle served by nginx, which proxies `/api/*` to the `backend` container
the same way the Vite dev server proxy does for `npm run dev`. If you'd
rather run with hot-reload during development, just start `postgres` alone
as shown above and skip to steps 4-5.

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

## Kubernetes Deployment

Manifests live in `k8s/` (plain YAML + a `kustomization.yaml` so you can
apply everything with one command). They deploy the same three containers
as `docker-compose.yml` — `postgres`, `backend`, `frontend` — as a
`Deployment`/`Service` pair each, in a dedicated `adherence-copilot`
namespace, plus an optional `Ingress`.

```
k8s/
├── namespace.yaml
├── postgres.yaml       # ConfigMap (schema.sql) + Secret + PVC + Deployment + Service
├── backend.yaml        # Secret + Deployment (2 replicas, /api/health probes) + Service
├── frontend.yaml       # Deployment (2 replicas) + Service
├── ingress.yaml         # optional - needs an ingress controller
└── kustomization.yaml
```

### 1. Build and push images

```bash
docker build -t your-registry/adherence-copilot-backend:latest ./backend
docker build -t your-registry/adherence-copilot-frontend:latest ./frontend
docker push your-registry/adherence-copilot-backend:latest
docker push your-registry/adherence-copilot-frontend:latest
```

Then update the `image:` lines in `k8s/backend.yaml` and `k8s/frontend.yaml`
to match. On a local cluster (kind/minikube) you can skip the registry
entirely and load images straight in instead:

```bash
kind load docker-image adherence-copilot-backend:latest adherence-copilot-frontend:latest
# or: minikube image load adherence-copilot-backend:latest
```

### 2. Set real secrets

`k8s/postgres.yaml` and `k8s/backend.yaml` each contain a `Secret` with
placeholder values (`CHANGE_ME_...`) so `kubectl apply -k k8s/` works
out of the box for a quick local demo — but don't commit real credentials
into those files. For anything beyond a throwaway local cluster, create
the secrets imperatively instead and delete the `Secret` objects from the
YAML you apply:

```bash
kubectl create namespace adherence-copilot
kubectl create secret generic postgres-secret -n adherence-copilot \
  --from-literal=POSTGRES_DB=adherence \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD=<a-real-password>
kubectl create secret generic backend-secret -n adherence-copilot \
  --from-literal=DATABASE_URL=postgresql://postgres:<same-password>@postgres:5432/adherence \
  --from-literal=ANTHROPIC_API_KEY=<your-real-key>
```

### 3. Apply the manifests

```bash
kubectl apply -k k8s/
kubectl get pods -n adherence-copilot -w
```

### 4. Access it

Without an ingress controller, port-forward:

```bash
kubectl port-forward -n adherence-copilot svc/frontend 5173:80
```

Open `http://localhost:5173`. With an ingress controller (e.g. ingress-nginx,
or the AWS Load Balancer Controller on EKS), use `k8s/ingress.yaml` instead —
point a real hostname at it, or add `<ingress-ip> adherence-copilot.local`
to `/etc/hosts` for local testing.

### 5. Populate data

Same pipeline as Docker Compose, just pointed at the cluster's Postgres via
port-forward:

```bash
kubectl port-forward -n adherence-copilot svc/postgres 5432:5432 &
python etl/etl.py
python ml/adherence_model.py   # uses ml/model/ if you've trained it, heuristic otherwise
```

### Notes

- `postgres.yaml` runs Postgres in-cluster with a `PersistentVolumeClaim` —
  fine for a demo, but prefer Amazon RDS for anything real: point
  `backend-secret`'s `DATABASE_URL` at RDS and skip deploying `postgres.yaml`
  entirely (same "just change `DATABASE_URL`" story as the rest of this repo).
- The schema-init caveat from Docker Compose applies here too: the
  `postgres-schema` ConfigMap is mounted at `/docker-entrypoint-initdb.d/`,
  which Postgres only runs against a fresh, empty PVC. If you need to
  re-apply it against an existing PVC, delete the PVC (`kubectl delete pvc
  postgres-pvc -n adherence-copilot`, which also deletes the data) or run
  `db/schema.sql` manually via `kubectl exec`.
- `frontend`'s nginx config proxies `/api/*` to a host literally named
  `backend` — that only resolves because the backend `Service` is named
  `backend` in the same namespace (Kubernetes DNS). Don't rename it without
  also updating `frontend/nginx.conf`.
- I don't have a Kubernetes cluster available to actually run these against,
  so they're verified for valid YAML and correct cross-references (Service
  names, ports, Secret keys) but not a live `kubectl apply`. Worth a real
  test run on kind/minikube before treating this as production-ready.

## Repo layout

```
respiratory-adherence-copilot/
├── docker-compose.yml # local Postgres (+ optional backend/frontend) for development
├── k8s/                # Kubernetes manifests (postgres/backend/frontend + ingress)
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
