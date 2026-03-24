# Repository layout

High-level map of this monorepo. Paths are from the repo root.

| Path | Role |
|------|------|
| `backend/` | FastAPI app: proxy (`/v1/*`), management API (`/api/v1/*`), migrations, tests |
| `admin-console/` | React admin SPA (policy, keys, billing, teams, experiments, analytics) |
| `web-app/` | Separate frontend (marketing or auxiliary UI — not the main admin console) |
| `sdk/python/` | PyPI package `openproxy-ai` |
| `sdk/typescript/` | npm package `openproxy-ai` |
| `deploy/helm/` | Kubernetes Helm chart for backend + console |
| `docs/` | User and operator documentation (this tree) |
| `plans/` | Internal planning notes (e.g. deployment runbooks) |

## Backend (`backend/app/`)

| Area | Contents |
|------|----------|
| `main.py` | App factory, routers, lifespan (scheduler jobs) |
| `routes/` | HTTP routers (`proxy`, `auth`, `billing`, `teams`, `experiments`, `analytics`, …) |
| `services/` | Business logic (`llm_service`, `policy_service`, `billing_service`, `metering_service`, …) |
| `models/` | SQLAlchemy ORM models |
| `schemas/` | Pydantic request/response models |
| `dependencies.py` | `get_db`, `get_redis`, JWT user, proxy API-key auth |
| `database.py` | Async engine/session, `set_session_org_id` for RLS |
| `config.py` | `settings` (pydantic-settings) — env-driven configuration |

## Tests

- `backend/tests/` — pytest suite (async); `pytest.ini` at `backend/pytest.ini`

## Migrations

- `backend/alembic/versions/` — Alembic revisions (chain order documented in [database-schema.md](./database-schema.md))
