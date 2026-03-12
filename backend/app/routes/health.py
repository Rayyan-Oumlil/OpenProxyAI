"""Health check endpoints — GET /health, GET /ready."""

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from fastapi.responses import JSONResponse

from app.config import settings
from app.dependencies import get_redis
from app.database import ping_db
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe — always 200, no external dependency checks."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "0.1.0",
    }


@router.get("/ready")
async def ready(redis: Redis = Depends(get_redis)) -> JSONResponse:
    """Readiness probe — verifies Postgres and Redis connectivity."""
    checks: dict[str, str] = {}

    # Postgres
    try:
        await ping_db()
        checks["postgres"] = "ok"
    except Exception:
        logger.exception("Postgres readiness check failed")
        checks["postgres"] = "unavailable"

    # Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        logger.exception("Redis readiness check failed")
        checks["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    body = {"status": "ready" if all_ok else "not ready", **checks}
    return JSONResponse(content=body, status_code=status_code)
