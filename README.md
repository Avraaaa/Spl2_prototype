# DataSoft Service Request Portal — uv + TypeScript-first agent starter

**Status:** real scaffold and health checks, **not** an implemented banking portal, a production release, or a proven safe fully autonomous deployment.

Architecture: React + strict TypeScript/Vite (`apps/web`) → Django + DRF (`services/api`) → PostgreSQL 18 + pgvector; private optional FastAPI service (`services/ml`) using Sentence-Transformers only when a vetted local model is provisioned. Django owns all persistent writes and tenant authorization. React and orchestration are TypeScript/JavaScript-first; Python is necessary for the fixed Django/FastAPI/ML stack.

## Prerequisites
- `uv` (Python **only**; installs Python 3.13 through `uv python install 3.13`), Node 24/npm, Git, Docker Desktop/Compose, Claude Code and Codex CLI (optional for basic bring-up).
- Native Windows (PowerShell) is the primary dev host; WSL2 and Docker are **not** required for local development.

## Native local development (Windows, no Docker)
Requires a local PostgreSQL 18 with pgvector (`C:\Program Files\PostgreSQL\18`).
```powershell
# one time, as the postgres superuser (creates synthetic local role/db + pgvector)
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -f scripts/dev-db-setup.sql
uv python install 3.13; uv sync --locked; npm ci --prefix apps/web
node scripts/dev.mjs seed     # synthetic demo banks, users and issues
node scripts/dev.mjs          # migrate, then Django :8000 + Vite :5173
node scripts/dev.mjs test     # Django + FastAPI + web checks
node scripts/dev.mjs lint     # ruff + mypy
```
`scripts/dev.mjs` holds synthetic local-only connection defaults; real environment variables override them.
- Internet access for **first-run dependency resolution**. This ZIP cannot contain verified lockfiles because its build environment could not connect to package registries. Before running CI or Docker, generate and commit both lockfiles on your own machine.

## First run (at repo root)
```bash
node scripts/bootstrap-agents.mjs
uv python install 3.13
uv lock
uv sync --locked
npm install --prefix apps/web --no-audit --no-fund
node scripts/validate-repo.mjs
# commit uv.lock and apps/web/package-lock.json before enabling CI or agents
git init
git add .
git commit -m "chore: bootstrap locked DataSoft foundation"
cp .env.example .env
# .env contains local synthetic credentials ONLY
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml exec -T api uv run --no-sync --package datasoft-api python services/api/manage.py migrate --noinput
curl http://localhost:8000/api/health/
curl http://localhost:8001/health
```

Open http://localhost:5173. This is a health-check landing screen; ticket features are tasks in `implementation.md`.

## Normal development
```bash
uv add --package datasoft-api <python-library>            # Django dependency
uv add --package datasoft-ml <python-library>             # ML service dependency
uv run --locked --package datasoft-api python services/api/manage.py check
uv run --locked --package datasoft-api pytest -q services/api/tests
uv run --locked --package datasoft-ml pytest -q services/ml/tests
uv run --locked ruff check services
uv run --locked pre-commit install    # optional local commit gates
npm ci --prefix apps/web && npm run --prefix apps/web check
node scripts/agent-runner.mjs --show
node scripts/agent-runner.mjs --task P0-T1
```
When approved Phase P5 starts, install optional ML model dependencies with `uv sync --extra model --package datasoft-ml`, pin a locally downloaded model checkpoint, evaluate Bangla/English test pairs, and keep model downloads **outside** default runtime. Never upload bank text to an external API.

## How AGENTS.md works with .gitignore
`AGENTS.md` **and `agents.md` are intentionally ignored** by Git. Their canonical, reviewed versions are tracked as `AGENTS.template.md` files at root and in service directories. `node scripts/bootstrap-agents.mjs` copies templates into local `AGENTS.md` files. `CLAUDE.md` imports root `@AGENTS.md`. Codex reads local root/nested `AGENTS.md` files. The JS worktree runner regenerates instructions inside each new Git worktree, even though ignored files are absent from Git. To change agent policy, edit a **tracked template** by separately approved review; local edits to ignored AGENTS.md are overwritten by bootstrap.

## Folder and workflow guide
- `docs/architecture.md`, `docs/security-invariants.md`, `docs/adr/`: design rationale and protected invariants.
- `docs/traceability.csv`: all 55 original requirements and implementation targets.
- `docs/tasks.json`, `implementation.md`: bounded phases and acceptance gates.
- `scripts/agent-runner.mjs`: optional local prototype-only Codex orchestrator (isolated Git worktree; gated review; no push or deployment).
- `.github/workflows/ci.yml`: independent structural, lint, TypeScript and PostgreSQL integration gates **once lockfiles are committed**.
- `docs/sources.md`: official docs and research links checked in November 2026.

## Explicit gaps
There is no precomputed lockfile, product authentication, tenant-safe issue CRUD, outbox worker, deployed inference model, complete OpenAPI contract or hardened production rollout yet. Stop your default Docker Compose stack before running the task runner: each task uses distinct published ports and a disposable Compose project, and cleans its database volume after gates. The later-profile `worker` is intentionally **disabled until P3-T2**. Production requires human threat review, secrets management, storage protection, backup restore demonstration and external audit-chain anchoring. See `docs/repository-status.md`.
