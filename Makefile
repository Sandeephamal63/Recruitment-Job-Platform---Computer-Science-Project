# Dev/prod commands for the recruitment platform.
# Docker-only: every target shells out to `docker-compose` (the standalone
# binary — the local Docker Desktop has no compose plugin). CI uses its own
# `docker compose` runner and is unaffected by this file.
#
# Run `make` (or `make help`) for the full target list.

COMPOSE      ?= docker-compose
PROD_COMPOSE ?= $(COMPOSE) -p recruit-prod -f docker-compose.prod.yml
SERVER       ?= $(COMPOSE) exec -T server
CLIENT       ?= $(COMPOSE) exec -T client
DB           ?= $(SERVER) python -m scripts.db_query
MONGO        ?= mongodb://mongo:27017/recruit
API_URL      ?= http://localhost:5001/api/health
PROXY_URL    ?= http://localhost:5173/api/health
PROD_URL     ?= http://localhost:8080/api/health

.DEFAULT_GOAL := help
.PHONY: help up build rebuild down down-volumes restart reload ps logs health \
        verify lint typecheck client-build test test-unit test-integration \
        bench eval seed shell shell-server shell-client shell-mongo mongo-logs \
        client-deps volumes client-node-modules \
        db-shell db-info db-collections db-indexes db-reindex db-user db-gridfs \
        db-embeddings db-expire-jobs db-funnel db-applicants db-pending db-distribution db-cv db-tokens \
        db-explain db-truncate db-reset db-seed db-dump db-restore \
        prod-up prod-down prod-logs prod-health

help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed -e 's/^## //' \
		| awk -F': ' '{ printf "  %-20s %s\n", $$1, $$2 }'

# === dev stack ================================================================
## up: build images if needed and start mongo + server + client detached
up:
	$(COMPOSE) up --build -d

## build: build the dev images only
build:
	$(COMPOSE) build

## rebuild: force-recreate the dev images, then start detached
rebuild:
	$(COMPOSE) up --build --force-recreate -d

## down: stop containers, keep the mongo data volume
down:
	$(COMPOSE) down

## down-volumes: stop containers AND delete the mongo data volume
down-volumes:
	$(COMPOSE) down -v

## restart: restart the dev stack (run this after a package.json change)
restart:
	$(COMPOSE) restart

## reload: recreate containers to pick up a changed docker-compose.yml
reload:
	$(COMPOSE) up -d --force-recreate

## ps: show dev container status
ps:
	$(COMPOSE) ps

## logs: tail logs from all dev services
logs:
	$(COMPOSE) logs -f

## health: curl the API directly and through the Vite proxy
health:
	@echo "API   $(API_URL)"; curl -fsS $(API_URL); echo
	@echo "proxy $(PROXY_URL)"; curl -fsS $(PROXY_URL); echo

## verify: lint, test, and build the client (the checks CI runs)
verify: lint test client-build

# === quality gates ============================================================
## lint: client TypeScript check (tsc --noEmit)
lint:
	$(CLIENT) npm run lint

## typecheck: alias of lint (the client is the only typechecked tier)
typecheck: lint

## client-build: tsc -b && vite build
client-build:
	$(CLIENT) npm run build

## test: run the full server pytest suite
test:
	$(SERVER) pytest

## test-unit: pytest without the slow integration marker
test-unit:
	$(SERVER) pytest -m "not integration"

## test-integration: only the slow tests (real models, live Mongo)
test-integration:
	$(SERVER) pytest -m integration

# === ml / data scripts ========================================================
## bench: measure matching latency against the <5s per-application NFR
bench:
	$(SERVER) python -m scripts.benchmark_matching

## eval: score the pipeline against the data/evaluation dataset
eval:
	$(SERVER) python -m scripts.evaluate_matching

## seed: seed a demo dataset (alias of db-seed; SEED_ARGS=--reset to replace)
seed: db-seed

# === shells ===================================================================
## shell: interactive bash inside the server container
shell: shell-server

## shell-server: bash inside the server container
shell-server:
	$(COMPOSE) exec server bash

## shell-client: sh inside the client container
shell-client:
	$(COMPOSE) exec client sh

## shell-mongo: mongosh against the dev database (alias of db-shell)
shell-mongo: db-shell

## mongo-logs: tail mongod logs
mongo-logs:
	$(COMPOSE) logs -f mongo

# === database operations ======================================================
# Read-only unless noted. `truncate` and `reindex` prompt for confirmation; pass
# YES=1 to skip. Add JSON=1 to any read target for machine-readable output. The
# full flag list lives in the script: `make shell-server python -m scripts.db_query --help`

## db-shell: interactive mongosh on the dev database
db-shell:
	$(COMPOSE) exec mongo mongosh $(MONGO)

## db-info: server, replica set, connections, and every database with its size
db-info:
	$(DB) info $(if $(JSON),--json)

## db-collections: per-collection document counts and sizes
db-collections:
	$(DB) collections $(if $(JSON),--json)

## db-indexes: all indexes, plus any missing from INDEX_SPECS (non-zero exit)
db-indexes:
	$(DB) indexes $(if $(COLLECTION),$(COLLECTION)) $(if $(JSON),--json)

## db-reindex: drop and recreate the declared indexes (confirm; YES=1 to skip)
db-reindex:
	$(DB) reindex $(if $(COLLECTION),$(COLLECTION)) $(if $(YES),--yes)

## db-embeddings: backfill job search embeddings (confirm; YES=1 to skip, ALL=1 for closed too)
db-embeddings:
	$(DB) embeddings $(if $(ALL),--all) $(if $(YES),--yes)

## db-expire-jobs: converge status=closed past deadlines (confirm; YES=1 to skip, DRY_RUN=1 to report)
db-expire-jobs:
	$(DB) expire-jobs $(if $(DRY_RUN),--dry-run) $(if $(YES),--yes)

## db-user: one user with their jobs, applications and funnel
db-user:
	@test -n "$(EMAIL)" || { echo "usage: make db-user EMAIL=someone@example.com"; false; }
	$(DB) user "$(EMAIL)" $(if $(JSON),--json)

## db-gridfs: stored CV files and which document holds each one
db-gridfs:
	$(DB) gridfs $(if $(JSON),--json)

## db-funnel: application counts per job and status (JOB_ID=... for one job)
db-funnel:
	$(DB) funnel $(if $(JOB_ID),$(JOB_ID)) $(if $(JSON),--json)

## db-applicants: a job's applicants with match score, skills and status
db-applicants:
	@test -n "$(JOB_ID)" || { echo "usage: make db-applicants JOB_ID=..."; false; }
	$(DB) applicants $(JOB_ID) $(if $(STATUS),--status $(STATUS)) \
		$(if $(MIN_SCORE),--min-score $(MIN_SCORE)) $(if $(SORT),--sort $(SORT)) \
		$(if $(LIMIT),--limit $(LIMIT)) $(if $(JSON),--json)

## db-pending: applications whose match result is still pending
db-pending:
	$(DB) pending $(if $(JSON),--json)

## db-distribution: match score histogram (JOB_ID=... for one job)
db-distribution:
	$(DB) distribution $(if $(JOB_ID),$(JOB_ID)) $(if $(JSON),--json)

## db-cv: a stored CV's extracted text beside its job and match result
db-cv:
	@test -n "$(APPLICATION_ID)" || { echo "usage: make db-cv APPLICATION_ID=..."; false; }
	$(DB) cv $(APPLICATION_ID) $(if $(CHARS),--chars $(CHARS)) $(if $(JSON),--json)

## db-tokens: refresh token counts per user (never prints secrets)
db-tokens:
	$(DB) tokens $(if $(JSON),--json)

## db-explain: query plan for a job's applicant list (index use, docs examined)
db-explain:
	@test -n "$(JOB_ID)" || { echo "usage: make db-explain JOB_ID=..."; false; }
	$(DB) explain $(JOB_ID)

## db-truncate: drop collections and re-apply indexes (confirm; YES=1 to skip)
db-truncate:
	$(DB) truncate $(if $(KEEP_CVS),--keep-cvs) $(if $(YES),--yes)

## db-reset: truncate, then re-seed the demo dataset (no prompt)
db-reset:
	$(DB) truncate --yes
	$(SERVER) python -m scripts.seed_demo

## db-seed: seed the demo dataset (SEED_ARGS=--reset to replace existing data)
db-seed:
	$(SERVER) python -m scripts.seed_demo $(SEED_ARGS)

## db-dump: archive the dev database into data/dumps on the host
db-dump:
	mkdir -p data/dumps
	$(COMPOSE) exec -T mongo mongodump --db recruit --archive --gzip \
		> data/dumps/recruit-$(shell date +%F-%H%M%S).archive.gz
	@ls -lh data/dumps

## db-restore: restore an archive (FILE=..., DRY_RUN=1 to validate, DROP=1 to replace)
db-restore:
	@test -n "$(FILE)" || { echo "usage: make db-restore FILE=data/dumps/<name>.archive.gz"; false; }
	$(COMPOSE) exec -T mongo mongorestore --archive --gzip --nsInclude='recruit.*' \
		$(if $(DRY_RUN),--dryRun,) $(if $(DROP),--drop,) < $(FILE)

# === client dependencies ======================================================
## client-deps: install client deps in the container, rebuild, restart
client-deps:
	@echo "required after editing package.json - never run npm on the host"
	$(COMPOSE) run --rm client npm install
	$(COMPOSE) build client
	$(COMPOSE) restart client

## volumes: list compose volumes
volumes:
	$(COMPOSE) volume ls

## client-node-modules: drop the stale node_modules volume to force a reseed
client-node-modules:
	$(COMPOSE) down
	docker volume rm recruitment-job-platform_client-node-modules || true
	$(COMPOSE) up -d

# === production stack =========================================================
## prod-up: build and start the prod stack on port 8080 (generates a JWT secret)
prod-up:
	JWT_SECRET_KEY=$$(openssl rand -hex 32) $(PROD_COMPOSE) up -d --build
	@echo "SPA http://localhost:8080"

## prod-down: stop the production stack and its volumes
prod-down:
	JWT_SECRET_KEY=x $(PROD_COMPOSE) down

## prod-logs: tail production logs
prod-logs:
	JWT_SECRET_KEY=x $(PROD_COMPOSE) logs -f

## prod-health: curl the production API through nginx
prod-health:
	@curl -fsS $(PROD_URL); echo
