# AI-Powered Recruitment Platform

Two-sided recruitment platform (MSc Computer Science project). Employers post jobs and
review applicants; candidates browse jobs and apply with a CV. On application, an NLP
pipeline scores the CV against the job description and returns matched skills, missing
skills, and recommendations to both sides. The system augments human hiring judgement —
it never makes or automates a hiring decision.

## Stack

| Tier            | Technology                                                        |
| --------------- | ----------------------------------------------------------------- |
| Frontend        | React 18 (Vite), TypeScript, Material UI v6, React Router, Axios  |
| Backend         | Python, Flask (app factory + blueprints), Flask-JWT-Extended      |
| Database        | MongoDB 7 (Docker container, pymongo) — `users`, `jobs`, `applications`, `matchResults` |
| AI / NLP        | spaCy, sentence-transformers, scikit-learn (M4+)                  |
| CV parsing      | pdfminer / docx2txt (M3+)                                         |
| Runtimes        | Docker Compose — Node 22 (client), Python 3.12 (server), Mongo 7  |

Nothing is installed on the host machine; all services run in Docker.

## Architecture

Three tiers: React SPA → Flask REST API (JWT-protected) → MongoDB.
AI matching lives in a swappable service layer (`server/app/services/matching_service.py`)
invoked by the API on application submission — it is not baked into route handlers, so it
stays independently testable. `users`/`jobs`/`applications`/`matchResults` are referenced
collections (not embedded), so dashboards query without duplicating large text fields.

See `docs/ARCHITECTURE.md` and `docs/DATA_MODEL.md`.

## Local run (Docker only)

Prerequisite: Docker Desktop (or any Docker daemon) running.

```bash
docker-compose up --build -d
```

> Use the standalone `docker-compose` binary locally (the Docker Desktop compose plugin is
> not guaranteed). CI (GitHub Actions) runs `docker compose` inside its own runner.

| Service | URL                                            |
| ------- | ---------------------------------------------- |
| React    | http://localhost:5173                          |
| API      | http://localhost:5001/api/health               |
| MongoDB  | mongodb://localhost:27017 (container `mongo`)  |

> Note: the API is published on host port **5001** because macOS AirPlay Receiver
> occupies port 5000 by default. Inside Docker the Vite proxy still reaches Flask on
> port 5000 via the compose network, so the browser path needs no change.

Verify connectivity:

```bash
curl http://localhost:5001/api/health
# -> {"status":"ok","db":"connected",...}

curl http://localhost:5173/api/health
# -> same payload, routed through the Vite dev proxy
```

Tests (backend) and matching benchmark:

```bash
docker-compose exec -T server pytest                         # full suite (matching, auth gating, CV parsing, e2e flows)
docker-compose exec -T server python -m scripts.benchmark_matching   # cold/warm latency vs the <5s per-application NFR
```

CI runs the same pytest suite against a Mongo service container (GitHub Actions). Tests
never download embedding models — unit tests inject stub embedders and the e2e flow uses
the TF-IDF scorer (`MATCH_EMBEDDINGS_DISABLED=true`); the real spaCy/sentence-transformers
pipeline is exercised by the benchmark and normal API use, where the models are installed
at image build.

## Database operations

`make <target>` for everything; `make` alone lists the targets. These answer the
questions the API cannot — which indexes exist, whether anything is orphaned, what
the stored CV text actually says.

```bash
make db-seed                  # realistic demo dataset (SEED_ARGS=--reset to replace)
make db-shell                 # interactive mongosh
make db-info                  # server, replica set, and every database with its size
make db-collections           # document counts and sizes per collection
make db-indexes               # all indexes + anything INDEX_SPECS declares but Mongo lacks
make db-user EMAIL=someone@example.com
make db-funnel                # applicants per job and status (JOB_ID=... for one job)
make db-applicants JOB_ID=... # applicants with match score, matched/missing skills
make db-pending               # applications the pipeline has not scored yet
make db-distribution          # match score histogram
make db-cv APPLICATION_ID=... # a stored CV's extracted text beside its match result
make db-gridfs                # stored CV files and which document holds each
make db-tokens                # refresh token counts per user (never prints secrets)
make db-explain JOB_ID=...    # query plan: index used, docs examined
make db-truncate              # drop collections, then re-apply indexes (prompts)
make db-reset                 # truncate + re-seed, the demo reset in one step
make db-dump                  # archive to data/dumps/ (git-ignored)
make db-restore FILE=data/dumps/recruit-….archive.gz DRY_RUN=1
```

`db-truncate` and `db-reindex` are the only commands that write: they print what they
will change and abort unless you type `yes` (pass `YES=1` to skip). Add `JSON=1` to any
read target for machine-readable output, or run the script directly for the full flag
list:

```bash
docker-compose exec -T server python -m scripts.db_query --help
```

Stop everything while preserving the database volume:

```bash
docker-compose down
```

Remove containers **and** the database:

```bash
docker-compose down -v
```

## Production (packaged deployment)

Multi-stage images (`server/Dockerfile.prod` — venv + baked ML models + gunicorn;
`client/Dockerfile.prod` — Vite build served by nginx, which also proxies `/api` to
the server). A real JWT secret is mandatory — the compose file refuses to start
without one:

```bash
JWT_SECRET_KEY=$(openssl rand -hex 32) docker-compose -p recruit-prod -f docker-compose.prod.yml up -d --build
curl http://localhost:8080/api/health
```

The SPA is single-origin at `http://localhost:8080`; the browser never talks to the
API directly. No host code is bind-mounted. Teardown (a throwaway secret is fine for
`down`, which never inspects the value):

```bash
JWT_SECRET_KEY=x docker-compose -p recruit-prod -f docker-compose.prod.yml down
```

Dev and prod stacks can run side by side (different container names, ports, and
project names); the prod stack is verified locally but **not** built in CI (its
model downloads would add minutes to every push — see `.github/workflows/ci.yml`).

## Bare-metal fallback (not required)

If you cannot run Docker, the services can run directly:

```bash
# server
cd server && python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
MONGO_URI=mongodb://localhost:27017/recruit flask --app run:app run

# client (separate terminal)
cd client && npm install
npm run dev
```

`vite.config.ts` reads `VITE_PROXY_TARGET` (defaults to `http://localhost:5000`), so the
proxy works on bare metal without changes.

## Project layout

```
client/   React SPA (Vite + TS + MUI)
server/   Flask app factory + blueprints + services
docs/     architecture + data model
```

## Milestones

- M0 Setup (this module): Dockerized monorepo, API health, UI shell.
- M1 Auth & Roles: JWT register/login, employer vs candidate.
- M2 Employer job CRUD, M3 Candidate browse/apply (parallel-safe).
- M4 AI matching v1: spaCy extraction + embeddings + scoring.
- M5 Explainability & dashboards: matched/missing skills, recommendations.
- M6 Hardening & testing, prod Docker images.
- M7 Evaluation: run against a realistic job/CV dataset, write report.