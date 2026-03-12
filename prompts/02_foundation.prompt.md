# Step 2 — Project Foundation

> **Reference:** Always follow the conventions, stack, and design decisions in `prompts/01_backend_backbone.prompt.md`. Do not deviate.

---

## Context

The repo is `Rayyan-Oumlil/OpenProxyAI`. The marketing website already exists in `web-app/`. We are now starting the backend. Nothing in `backend/` exists yet.

---

## What To Build This Session

Create the project foundation — the skeleton that everything else will be built on top of. No application logic yet, just structure, dependencies, and infrastructure.

### 1. Directory skeleton

Create every folder and `__init__.py` placeholder file in `backend/` as specified in the master prompt. Files that aren't implemented yet should contain only a module docstring explaining what they'll do — no `pass`, no `TODO` comments, no empty files.

### 2. `backend/requirements.txt`

Exact pinned versions from the master prompt. Split into sections with comments:
```
# Web framework
# LLM
# Database
# Cache
# Auth
# Observability
# Dev/test
```

### 3. `backend/Dockerfile`

Multi-stage build:
- Stage 1 (`builder`): install dependencies into a venv
- Stage 2 (`runtime`): copy venv, copy app, run as non-root user `appuser`
- `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- `HEALTHCHECK` hitting `/health`

### 4. `docker-compose.yml` (at repo root)

Exactly as specified in the master prompt:
- `api` service (builds `./backend`, port 8000, hot reload via volume mount)
- `postgres:16-alpine` with healthcheck
- `redis:7-alpine` with healthcheck
- Named volumes for data persistence
- All credentials from env vars with safe dev defaults

### 5. `backend/.env.example`

All env vars from the master prompt, grouped and commented. No real secrets.

### 6. `backend/alembic.ini` + `backend/alembic/env.py`

Standard Alembic setup wired to read `DATABASE_URL` from environment. `env.py` must use async engine (`asyncpg`).

### 7. `backend/README.md`

Quick start only — 10 lines max:
```bash
cp .env.example .env
# edit .env with your API keys
docker compose up -d
cd backend && alembic upgrade head
uvicorn app.main:app --reload
```

---

## Done When

Run these in order — all must succeed:

```bash
# From repo root
docker compose up -d

# Postgres is healthy
docker compose ps   # api, postgres, redis all show "healthy" or "running"

# Connect to Postgres
docker compose exec postgres psql -U openproxyai -c "\l"
# → shows "openproxyai" database

# Connect to Redis
docker compose exec redis redis-cli ping
# → PONG
```

Nothing needs to run at `localhost:8000` yet — that's Step 3.
