# Step 3 — FastAPI App Skeleton

> **Reference:** Follow `prompts/01_backend_backbone.prompt.md` for all conventions. Step 2 (foundation) is already complete — `docker compose up -d` works.

---

## Context

The folder structure, Docker setup, and Alembic config exist. Now bring the FastAPI app to life — just enough to start, respond to `/health`, and serve the auto-generated OpenAPI docs. No business logic yet.

---

## What To Build This Session

### 1. `backend/app/config.py`

Use `pydantic-settings` (`BaseSettings`). Load everything from environment variables. Include:
- `APP_NAME`, `APP_ENV`, `DEBUG`
- `SECRET_KEY`
- `DATABASE_URL` (asyncpg)
- `REDIS_URL`
- `CORS_ORIGINS` (parsed as `list[str]`)
- `DEFAULT_RATE_LIMIT_RPM`, `DEFAULT_RATE_LIMIT_TPM`, `DEFAULT_BUDGET_DAILY_USD`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (optional, for dev convenience)

Export a single `settings = Settings()` instance.

### 2. `backend/app/utils/logging.py`

Configure structured JSON logging for the entire app:
- Use Python's `logging` module
- JSON format: `{"timestamp": ..., "level": ..., "logger": ..., "message": ..., "request_id": ...}`
- `request_id` injected via `contextvars.ContextVar` (set per-request in middleware)
- Log level from `settings.DEBUG`

Export `get_logger(name: str) -> logging.Logger`.

### 3. `backend/app/middleware/request_id.py`

FastAPI `BaseHTTPMiddleware`:
- Generate a UUID v4 per request
- Store in `ContextVar` (for logging)
- Inject as `X-OpenProxyAI-Request-Id` response header

### 4. `backend/app/middleware/timing.py`

FastAPI `BaseHTTPMiddleware`:
- Record `time.perf_counter()` before calling `call_next`
- Inject `X-OpenProxyAI-Latency-Ms` response header (integer milliseconds)

### 5. `backend/app/middleware/cors.py`

`CORSMiddleware` configured from `settings.CORS_ORIGINS`. Allow all methods and headers (tightened in production).

### 6. `backend/app/database.py`

Async SQLAlchemy setup:
- `create_async_engine` with `DATABASE_URL`
- `AsyncSessionLocal` session factory
- `get_db()` async generator for `Depends()`
- `ping_db()` async function that runs `SELECT 1` (used in `/ready`)

### 7. `backend/app/routes/health.py`

Two endpoints:

`GET /health` — always returns 200, no DB check:
```json
{"status": "healthy", "app": "OpenProxyAI", "version": "0.1.0"}
```

`GET /ready` — checks DB + Redis connectivity:
```json
{"status": "ready", "postgres": "ok", "redis": "ok"}
```
Returns 503 with `{"status": "not ready", "detail": "..."}` if either check fails.

### 8. `backend/app/main.py`

FastAPI app factory with:
- `lifespan` context manager: connect/verify DB + Redis on startup, log startup message, disconnect on shutdown
- Add middleware in order: CORS → RequestID → Timing
- Include health router (no prefix)
- `app.title = "OpenProxyAI"`, `app.version = "0.1.0"`, `app.description = "Zero Trust AI Gateway"`
- Disable the default `/docs` redirect to `/redoc` (keep both, just clean up)
- Custom OpenAPI tags for grouping: `Proxy`, `Auth`, `API Keys`, `Users`, `Analytics`

---

## Done When

```bash
# Start the app (Postgres + Redis already running from Step 2)
cd backend
uvicorn app.main:app --reload --port 8000

# Health check
curl http://localhost:8000/health
# → {"status":"healthy","app":"OpenProxyAI","version":"0.1.0"}

# Readiness check
curl http://localhost:8000/ready
# → {"status":"ready","postgres":"ok","redis":"ok"}

# Check headers are injected
curl -I http://localhost:8000/health
# → X-OpenProxyAI-Request-Id: <uuid>
# → X-OpenProxyAI-Latency-Ms: <number>

# Swagger UI loads
# Open http://localhost:8000/docs in browser → full UI with tag groups visible
```
