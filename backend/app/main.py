"""FastAPI app factory with middleware, lifespan, and all routers."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.middleware.cors import add_cors_middleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.timing import TimingMiddleware
from app.routes.auth import router as auth_router
from app.routes.api_keys import router as api_keys_router
from app.routes.analytics import router as analytics_router
from app.routes.health import router as health_router
from app.routes.proxy import router as proxy_router
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# ── OpenAPI tag metadata ────────────────────────────────────────────
TAGS_METADATA = [
    {"name": "Health", "description": "Liveness and readiness probes"},
    {"name": "Proxy", "description": "LLM proxy / chat completions"},
    {"name": "Auth", "description": "Authentication and token management"},
    {"name": "API Keys", "description": "API key CRUD"},
    {"name": "Users", "description": "User management"},
    {"name": "Analytics", "description": "Usage analytics and cost tracking"},
]


async def refresh_materialized_view() -> None:
    """Refresh analytics materialized view without blocking API requests."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_spend"))
            await session.commit()
        logger.info("mv_daily_spend refreshed")
    except Exception:
        logger.exception("Failed to refresh mv_daily_spend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: connect DB + Redis → app.state.  Shutdown: dispose."""
    setup_logging()
    logger.info(
        "Starting %s env=%s debug=%s",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.DEBUG,
    )

    # Redis — explicit pool for high-throughput rate limiting
    app.state.redis = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
    )

    # DB engine is already created at import time (app.database)
    app.state.db_engine = engine

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        refresh_materialized_view,
        "interval",
        minutes=5,
        id="refresh_mv_daily_spend",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    logger.info("Startup complete — ready to serve traffic")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down …")
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await app.state.redis.aclose()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="Zero Trust AI Gateway",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=TAGS_METADATA,
)

# ── Middleware (execution order: CORS → RequestID → Timing) ─────────
# Added in reverse because Starlette wraps outer-first.
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIdMiddleware)
add_cors_middleware(app)

# ── Routers ─────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(api_keys_router)
app.include_router(proxy_router)
app.include_router(analytics_router)


# ── Global exception handler — never leak stack traces ──────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": "An unexpected error occurred"},
    )
