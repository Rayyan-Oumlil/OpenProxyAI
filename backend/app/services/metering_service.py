"""Hourly Stripe usage-record sync for metered plans (sidecar — never fails the app).

Aggregates token usage from ``request_logs`` per UTC hour (``mv_daily_spend`` is daily-only).
Reports increments to Stripe with idempotency keys ``opai-meter-{org_id}-{YYYYMMDDHH}``.

Uses ``set_session_org_id`` before reading ``request_logs`` so RLS (``app.current_org_id``)
allows rows for that org. Each org uses a **short-lived** DB session so connections are
not held across Stripe HTTP calls.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, set_session_org_id
from app.models.organization import Organization
from app.services.billing_service import _subscription_item_price_id

logger = logging.getLogger(__name__)


def _stripe_get(obj: Any, *path: str, default: Any = None) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return default if cur is None else cur


def meter_idempotency_key(org_id: UUID, hour_start: datetime) -> str:
    """Stable idempotency key for one org + UTC hour bucket."""
    if hour_start.tzinfo is None:
        hour_start = hour_start.replace(tzinfo=UTC)
    else:
        hour_start = hour_start.astimezone(UTC)
    return f"opai-meter-{org_id}-{hour_start.strftime('%Y%m%d%H')}"


def clamp_window_to_subscription_period(
    hour_start: datetime,
    hour_end: datetime,
    period_start_ts: int,
    now: datetime,
) -> tuple[datetime, datetime]:
    """Return the intersection of [hour_start, hour_end) with [period_start, now)."""
    if hour_start.tzinfo is None:
        hour_start = hour_start.replace(tzinfo=UTC)
    else:
        hour_start = hour_start.astimezone(UTC)
    if hour_end.tzinfo is None:
        hour_end = hour_end.replace(tzinfo=UTC)
    else:
        hour_end = hour_end.astimezone(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)
    period_start = datetime.fromtimestamp(period_start_ts, tz=UTC)
    effective_start = max(hour_start, period_start)
    effective_end = min(hour_end, now)
    return effective_start, effective_end


def _trusted_cached_subscription_item_id(
    subscription: Any,
    cached_si: str | None,
    metered_price: str,
) -> str | None:
    """Return cached ``si_`` only if it appears on this subscription with the metered price."""
    if not cached_si or not metered_price:
        return None
    items = _stripe_get(subscription, "items", "data", default=[]) or []
    if not isinstance(items, list):
        return None
    for item in items:
        if str(_stripe_get(item, "id", default="") or "") != cached_si:
            continue
        if _subscription_item_price_id(item) == metered_price:
            return cached_si
    return None


class MeteringService:
    @staticmethod
    def _stripe_configured() -> bool:
        return bool(
            getattr(settings, "STRIPE_SECRET_KEY", "")
            and getattr(settings, "STRIPE_METERED_PRICE_ID", "")
        )

    @staticmethod
    async def _tokens_in_window(
        db: AsyncSession,
        org_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        row = (
            await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS tokens
                    FROM request_logs
                    WHERE org_id = :org_id
                      AND archived_at IS NULL
                      AND created_at >= :start
                      AND created_at < :end
                    """
                ),
                {
                    "org_id": str(org_id),
                    "start": window_start,
                    "end": window_end,
                },
            )
        ).mappings().one()
        return int(row["tokens"] or 0)

    @staticmethod
    async def _request_logs_tokens_period(
        db: AsyncSession,
        org_id: UUID,
        period_start: datetime,
        period_end_exclusive: datetime,
    ) -> int:
        """Sum tokens in ``request_logs`` for diagnostics (matches hourly query semantics)."""
        row = (
            await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS tokens
                    FROM request_logs
                    WHERE org_id = :org_id
                      AND archived_at IS NULL
                      AND created_at >= :start
                      AND created_at < :end
                    """
                ),
                {
                    "org_id": str(org_id),
                    "start": period_start,
                    "end": period_end_exclusive,
                },
            )
        ).mappings().one()
        return int(row["tokens"] or 0)

    @staticmethod
    def _resolve_metered_subscription_item_id(
        subscription: Any,
        cached_item_id: str | None,
    ) -> str | None:
        metered_price = getattr(settings, "STRIPE_METERED_PRICE_ID", "") or ""
        if not metered_price:
            return None
        items = _stripe_get(subscription, "items", "data", default=[]) or []
        if not isinstance(items, list):
            return None
        for item in items:
            if _subscription_item_price_id(item) == metered_price:
                raw = _stripe_get(item, "id")
                if raw:
                    return str(raw)
        trusted = _trusted_cached_subscription_item_id(
            subscription, cached_item_id, metered_price
        )
        return trusted

    @staticmethod
    def _retrieve_subscription(subscription_id: str) -> Any:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe.Subscription.retrieve(subscription_id)

    @staticmethod
    def _submit_usage_record(
        subscription_item_id: str,
        quantity: int,
        timestamp_unix: int,
        idempotency_key: str,
    ) -> None:
        """POST /v1/subscription_items/{id}/usage_records (SDK v14+ omits a public helper).

        ``idempotency_key`` must be passed as a keyword argument to ``_static_request`` so the
        SDK sends it as the ``Idempotency-Key`` HTTP header. Placing it inside the params dict
        would send it as a POST body field, which Stripe ignores — causing double-billing on
        any retry.
        """
        stripe.api_key = settings.STRIPE_SECRET_KEY
        url = f"/v1/subscription_items/{subscription_item_id}/usage_records"
        stripe.SubscriptionItem._static_request(
            "post",
            url,
            {
                "quantity": quantity,
                "timestamp": timestamp_unix,
                "action": "increment",
            },
            idempotency_key=idempotency_key,
        )

    async def sync_hourly_metered_usage(self) -> None:
        """Sync previous UTC hour token usage to Stripe for all active metered orgs."""
        if not getattr(settings, "METERED_SYNC_ENABLED", True):
            return
        if not self._stripe_configured():
            return

        now = datetime.now(UTC)
        hour_end = now.replace(minute=0, second=0, microsecond=0)
        hour_start = hour_end - timedelta(hours=1)

        async with AsyncSessionLocal() as db:
            result = await db.scalars(
                select(Organization).where(
                    func.lower(Organization.plan) == "metered",
                    Organization.is_active.is_(True),
                    Organization.stripe_subscription_id.isnot(None),
                    Organization.stripe_subscription_status == "active",
                )
            )
            orgs = list(result.all())

        for org in orgs:
            try:
                await self._sync_one_org(org, hour_start, hour_end, now)
            except Exception:
                logger.warning(
                    "metered usage sync skipped for org %s",
                    org.id,
                    exc_info=True,
                )

    async def _sync_one_org(
        self,
        org: Organization,
        hour_start: datetime,
        hour_end: datetime,
        now: datetime,
    ) -> None:
        sub_id = org.stripe_subscription_id
        if not sub_id:
            return

        subscription = await asyncio.to_thread(self._retrieve_subscription, str(sub_id))
        period_start_ts = int(_stripe_get(subscription, "current_period_start", default=0) or 0)
        period_end_ts = int(_stripe_get(subscription, "current_period_end", default=0) or 0)
        if period_start_ts <= 0:
            return

        period_end = datetime.fromtimestamp(period_end_ts, tz=UTC)
        eff_start, eff_end = clamp_window_to_subscription_period(
            hour_start, hour_end, period_start_ts, now
        )
        if eff_start >= eff_end:
            return

        cached_si = None
        settings_map = org.settings or {}
        if isinstance(settings_map, dict):
            raw = settings_map.get("stripe_metered_subscription_item_id")
            if isinstance(raw, str) and raw:
                cached_si = raw

        si_id = self._resolve_metered_subscription_item_id(subscription, cached_si)
        if not si_id:
            logger.warning("No metered subscription item for org %s", org.id)
            return

        async with AsyncSessionLocal() as db:
            await set_session_org_id(db, org.id)
            tokens = await self._tokens_in_window(db, org.id, eff_start, eff_end)

            period_start_dt = datetime.fromtimestamp(period_start_ts, tz=UTC)
            diag_end = min(period_end, now)
            try:
                if diag_end > period_start_dt:
                    diag_tokens = await self._request_logs_tokens_period(
                        db, org.id, period_start_dt, diag_end
                    )
                    logger.debug(
                        "metered sync org=%s hour=%s tokens_hour=%s period_tokens_logs=%s",
                        org.id,
                        hour_start.isoformat(),
                        tokens,
                        diag_tokens,
                    )
            except Exception:
                logger.warning(
                    "metered diagnostic token sum failed for org %s",
                    org.id,
                    exc_info=True,
                )

        if tokens <= 0:
            return

        idem = meter_idempotency_key(org.id, hour_start)
        ts_report = int(eff_end.timestamp())

        await asyncio.to_thread(
            self._submit_usage_record,
            si_id,
            tokens,
            ts_report,
            idem,
        )


metering_service = MeteringService()


async def run_hourly_metered_sync() -> None:
    """APScheduler entrypoint: swallow all errors (sidecar)."""
    try:
        await metering_service.sync_hourly_metered_usage()
    except Exception:
        logger.warning("hourly metered sync job failed", exc_info=True)
