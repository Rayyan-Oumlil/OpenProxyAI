"""FastAPI app factory with middleware, lifespan, and all routers."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from app.config import settings
from app.database import AsyncSessionLocal, engine, set_session_org_id
from app.models.webhook_delivery import WebhookDelivery
from app.middleware.cors import add_cors_middleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.timing import TimingMiddleware
from app.routes.admin_audit import router as admin_audit_router
from app.routes.auth import router as auth_router
from app.routes.api_keys import router as api_keys_router
from app.routes.analytics import router as analytics_router
from app.routes.billing import router as billing_router
from app.routes.health import router as health_router
from app.routes.invites import router as invites_router
from app.routes.organizations import router as organizations_router
from app.routes.playground import router as playground_router
from app.routes.provider_keys import router as provider_keys_router
from app.routes.experiments import router as experiments_router
from app.routes.requests import router as requests_router
from app.routes.teams import router as teams_router
from app.routes.proxy import router as proxy_router
from app.routes.sso import router as sso_router
from app.routes.metrics import router as metrics_router
from app.routes.users import router as users_router
from app.models.organization import Organization
from app.services.metering_service import run_hourly_metered_sync
from app.services.provider_health_service import run_provider_health_check
from app.services.spend_batch_service import run_flush_request_logs_batch
from app.services.key_rotation_scheduler import run_key_rotation
from app.services.adaptive_sampling_service import run_adaptive_sampling_job
from app.services.spend_report_service import run_monthly_spend_reports, run_weekly_spend_reports
from app.services.webhook_service import _deliver as _webhook_deliver
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# ── OpenAPI tag metadata ────────────────────────────────────────────
TAGS_METADATA = [
    {"name": "Health", "description": "Liveness and readiness probes"},
    {"name": "Proxy", "description": "LLM proxy / chat completions"},
    {"name": "Auth", "description": "Authentication and token management"},
    {"name": "API Keys", "description": "API key CRUD"},
    {"name": "Users", "description": "User management"},
    {"name": "Organizations", "description": "Organization settings"},
    {"name": "Provider Keys", "description": "LLM provider key management"},
    {"name": "Experiments", "description": "Model A/B testing with traffic splitting"},
    {"name": "Requests", "description": "Request scores for experiment quality evaluation"},
    {"name": "Teams", "description": "Team/project scoping for cost attribution"},
    {"name": "Analytics", "description": "Usage analytics and cost tracking"},
    {"name": "Invites", "description": "Team member invite management"},
    {"name": "SSO", "description": "OIDC/SSO connection management"},
    {"name": "Metrics", "description": "Prometheus metrics endpoint"},
    {"name": "Admin Audit", "description": "Admin action audit log (SOC 2)"},
    {"name": "Billing", "description": "Stripe billing management"},
    {"name": "Playground", "description": "Prompt playground and model comparison"},
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


async def archive_old_logs() -> None:
    """Mark request_logs older than the org's audit retention period as archived."""
    from sqlalchemy import update as sa_update

    from app.config import PLAN_FEATURES
    from app.models.organization import Organization
    from app.models.request_log import RequestLog

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Organization).where(Organization.is_active == True)  # noqa: E712
            )
            orgs = result.scalars().all()

            for org in orgs:
                await set_session_org_id(session, org.id)
                plan = (org.plan or "free").lower()
                retention_days = PLAN_FEATURES.get(plan, PLAN_FEATURES["free"])["audit_retention_days"]
                cutoff = datetime.now(UTC) - timedelta(days=retention_days)

                await session.execute(
                    sa_update(RequestLog)
                    .where(
                        RequestLog.org_id == org.id,
                        RequestLog.created_at < cutoff,
                        RequestLog.archived_at.is_(None),
                    )
                    .values(archived_at=datetime.now(UTC))
                )
            await session.commit()
        logger.info("archive_old_logs complete")
    except Exception:
        logger.exception("Failed to archive old logs")


async def retry_failed_webhooks() -> None:
    """Retry failed webhook deliveries with exponential backoff.

    Uses _deliver() which handles SSRF validation, HMAC signing, and retries.
    Sets org_id per org for RLS when querying webhook_deliveries.
    """
    try:
        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        async with AsyncSessionLocal() as db:
            orgs_result = await db.scalars(
                select(Organization).where(Organization.is_active == True)  # noqa: E712
            )
            orgs = list(orgs_result.all())

            total_processed = 0
            for org in orgs:
                await set_session_org_id(db, org.id)
                result = await db.scalars(
                    select(WebhookDelivery)
                    .where(
                        WebhookDelivery.org_id == org.id,
                        WebhookDelivery.status == "failed",
                        WebhookDelivery.attempt_count < 3,
                        WebhookDelivery.last_attempted_at < cutoff,
                    )
                    .limit(50)
                )
                deliveries = result.all()
                total_processed += len(deliveries)

                for delivery in deliveries:
                    backoff_seconds = (5 ** delivery.attempt_count) * 60
                    elapsed = (datetime.now(UTC) - delivery.last_attempted_at.replace(tzinfo=UTC)).total_seconds()
                    if elapsed < backoff_seconds:
                        continue

                    # delivery.org_id == org.id (we filtered by org); use org directly
                    org_settings = getattr(org, "settings", None) or {}
                    secret = (org_settings.get("webhooks") or {}).get("secret", "") or ""

                    new_status, http_status = await _webhook_deliver(
                        delivery.url, delivery.payload, secret,
                    )

                    if new_status == "delivered":
                        delivery.status = "delivered"
                        delivery.http_status = http_status
                    else:
                        delivery.attempt_count += 1
                        delivery.last_attempted_at = datetime.now(UTC)
                        if delivery.attempt_count >= 3:
                            delivery.status = "exhausted"

            await db.commit()
        logger.info("retry_failed_webhooks complete — processed %d deliveries", total_processed)
    except Exception:
        logger.exception("retry_failed_webhooks job failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: connect DB + Redis → app.state.  Shutdown: dispose."""
    setup_logging()

    _DEFAULT_SECRET = "dev-secret-key-change-in-production"
    if settings.APP_ENV != "development" and settings.SECRET_KEY == _DEFAULT_SECRET:
        raise RuntimeError(
            "SECRET_KEY must be changed from its default value in non-development environments. "
            "Set the SECRET_KEY environment variable to a strong random string."
        )
    if len(settings.SECRET_KEY) < 32:
        raise RuntimeError(
            "SECRET_KEY must be at least 32 characters. "
            "Generate with: openssl rand -hex 32"
        )
    if settings.STRIPE_SECRET_KEY and not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET is required when STRIPE_SECRET_KEY is set")

    if settings.AIRGAP_MODE:
        logger.info("AIRGAP_MODE enabled — Langfuse, ClickHouse, spend reports, and Stripe metered sync disabled")

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
    scheduler.add_job(
        archive_old_logs,
        "interval",
        hours=1,
        id="archive_old_logs",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        retry_failed_webhooks,
        "interval",
        minutes=5,
        id="retry_failed_webhooks",
        max_instances=1,
        coalesce=True,
    )
    if not settings.AIRGAP_MODE:
        scheduler.add_job(
            run_hourly_metered_sync,
            "interval",
            hours=1,
            id="hourly_metered_stripe_sync",
            max_instances=1,
            coalesce=True,
        )
    if settings.BATCH_SPEND_ENABLED:
        scheduler.add_job(
            run_flush_request_logs_batch,
            "interval",
            seconds=settings.BATCH_SPEND_FLUSH_INTERVAL_SECONDS,
            id="flush_request_logs_batch",
            max_instances=1,
            coalesce=True,
        )
    if settings.PROVIDER_HEALTH_CHECK_ENABLED:
        scheduler.add_job(
            run_provider_health_check,
            "interval",
            minutes=5,
            id="provider_health_check",
            max_instances=1,
            coalesce=True,
        )
    if not settings.AIRGAP_MODE:
        scheduler.add_job(
            run_weekly_spend_reports,
            "cron",
            day_of_week="mon",
            hour=9,
            minute=0,
            id="weekly_spend_reports",
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            run_monthly_spend_reports,
            "cron",
            day=1,
            hour=9,
            minute=0,
            id="monthly_spend_reports",
            max_instances=1,
            coalesce=True,
        )
    if settings.KEY_ROTATION_SCHEDULER_ENABLED:
        scheduler.add_job(
            run_key_rotation,
            "interval",
            days=settings.KEY_ROTATION_INTERVAL_DAYS,
            id="key_rotation",
            max_instances=1,
            coalesce=True,
        )
    if settings.ADAPTIVE_LB_ENABLED:
        scheduler.add_job(
            run_adaptive_sampling_job,
            "interval",
            minutes=settings.ADAPTIVE_LB_SAMPLE_MINUTES,
            id="adaptive_lb_sampling",
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

# ── Middleware (execution order: CORS → RequestID → Timing → Security) ─────
# Added in reverse because Starlette wraps outer-first.
# SecurityHeadersMiddleware is added last so it runs first and injects headers
# on every response, including error responses from inner middleware.


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject SOC 2 / HIPAA-required HTTP security headers on every response."""

    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIdMiddleware)
add_cors_middleware(app)
app.add_middleware(SecurityHeadersMiddleware)

# ── Routers ─────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(api_keys_router)
app.include_router(users_router)
app.include_router(organizations_router)
app.include_router(provider_keys_router)
app.include_router(experiments_router)
app.include_router(requests_router)
app.include_router(teams_router)
app.include_router(proxy_router)
app.include_router(analytics_router)
app.include_router(invites_router)
app.include_router(sso_router)
app.include_router(admin_audit_router)
app.include_router(billing_router)
app.include_router(playground_router)

if settings.PROMETHEUS_ENABLED:
    app.include_router(metrics_router)


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
