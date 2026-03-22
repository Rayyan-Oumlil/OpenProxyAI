"""Weekly/monthly spend report service — Slack webhook or email digest per org."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, set_session_org_id
from app.models.organization import Organization

logger = logging.getLogger(__name__)


def _get_spend_report_destinations(org: Organization) -> tuple[str | None, str | None]:
    """Extract Slack webhook and/or email from org settings."""
    s = org.settings or {}
    spend = s.get("spend_report") or {}
    webhook = spend.get("webhook") or s.get("spend_report_webhook")
    email = spend.get("email") or s.get("spend_report_email")
    return (webhook, email)


async def _get_spend_for_period(
    db: AsyncSession,
    org_id: UUID,
    since: datetime,
    until: datetime,
) -> dict:
    """Sum cost_usd and token counts from request_logs for the period."""
    result = (
        await db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                    COALESCE(SUM(total_tokens), 0)::bigint AS total_tokens,
                    COALESCE(COUNT(*), 0)::bigint AS total_requests
                FROM request_logs
                WHERE org_id = :org_id
                  AND created_at >= :since
                  AND created_at < :until
                  AND archived_at IS NULL
                """
            ),
            {"org_id": org_id, "since": since, "until": until},
        )
    ).mappings().one()
    return dict(result)


def _format_slack_message(
    org_name: str,
    period_label: str,
    total_cost_usd: float,
    total_tokens: int,
    total_requests: int,
) -> dict:
    """Format spend summary for Slack webhook."""
    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"OpenProxyAI — {period_label} Spend Report", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Organization:*\n{org_name}"},
                    {"type": "mrkdwn", "text": f"*Period:*\n{period_label}"},
                    {"type": "mrkdwn", "text": f"*Total cost:*\n${total_cost_usd:.2f} USD"},
                    {"type": "mrkdwn", "text": f"*Requests:*\n{total_requests:,}"},
                    {"type": "mrkdwn", "text": f"*Tokens:*\n{total_tokens:,}"},
                ],
            },
        ],
    }


def _format_email_subject(org_name: str, period_label: str) -> str:
    return f"OpenProxyAI — {period_label} Spend Report for {org_name}"


def _format_email_body(
    org_name: str,
    period_label: str,
    total_cost_usd: float,
    total_tokens: int,
    total_requests: int,
) -> str:
    return f"""OpenProxyAI Spend Report

Organization: {org_name}
Period: {period_label}

Total cost: ${total_cost_usd:.2f} USD
Total requests: {total_requests:,}
Total tokens: {total_tokens:,}
"""


async def _send_to_slack(webhook_url: str, payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(webhook_url, json=payload)
            return r.status_code == 200
    except Exception as e:
        logger.warning("Slack webhook failed: %s", e)
        return False


async def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Send via SendGrid if configured."""
    api_key = getattr(settings, "SENDGRID_API_KEY", "") or ""
    from_email = getattr(settings, "EMAIL_FROM", "") or "noreply@openproxyai.com"
    if not api_key:
        logger.debug("SENDGRID_API_KEY not set, skipping email")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "personalizations": [{"to": [{"email": to_email}]}],
                    "from": {"email": from_email, "name": "OpenProxyAI"},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
            )
            return r.status_code in (200, 202)
    except Exception as e:
        logger.warning("SendGrid email failed: %s", e)
        return False


async def send_weekly_report(org_id: UUID) -> bool:
    """Send weekly spend report for an org. Returns True if at least one delivery succeeded."""
    now = datetime.now(UTC)
    since = now - timedelta(days=7)
    return await _send_spend_report(org_id, since, now, "Weekly (7 days)")


async def send_monthly_report(org_id: UUID) -> bool:
    """Send monthly spend report for an org. Returns True if at least one delivery succeeded."""
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return await _send_spend_report(org_id, month_start, now, "Monthly (MTD)")


async def _send_spend_report(
    org_id: UUID,
    since: datetime,
    until: datetime,
    period_label: str,
) -> bool:
    webhook, email = None, None
    org_name = ""
    async with AsyncSessionLocal() as db:
        org = await db.get(Organization, org_id)
        if org is None:
            return False
        webhook, email = _get_spend_report_destinations(org)
        if not webhook and not email:
            return False
        org_name = org.name
        await set_session_org_id(db, org_id)
        data = await _get_spend_for_period(db, org_id, since, until)

    total_cost = float(data["total_cost_usd"] or 0)
    total_tokens = int(data["total_tokens"] or 0)
    total_requests = int(data["total_requests"] or 0)

    success = False
    if webhook:
        payload = _format_slack_message(
            org_name, period_label, total_cost, total_tokens, total_requests
        )
        if await _send_to_slack(webhook, payload):
            success = True
    if email:
        subject = _format_email_subject(org_name, period_label)
        body = _format_email_body(
            org_name, period_label, total_cost, total_tokens, total_requests
        )
        if await _send_email(email, subject, body):
            success = True
    return success


async def run_weekly_spend_reports() -> None:
    """Scheduler job: send weekly reports to orgs with spend_report configured."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.scalars(
                select(Organization).where(Organization.is_active.is_(True))
            )
            orgs = list(result.all())

        for org in orgs:
            webhook, email = _get_spend_report_destinations(org)
            if webhook or email:
                await send_weekly_report(org.id)

        logger.debug("Weekly spend reports complete — %d orgs", len(orgs))
    except Exception:
        logger.exception("Weekly spend reports job failed")


async def run_monthly_spend_reports() -> None:
    """Scheduler job: send monthly reports to orgs with spend_report configured."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.scalars(
                select(Organization).where(Organization.is_active.is_(True))
            )
            orgs = list(result.all())

        for org in orgs:
            webhook, email = _get_spend_report_destinations(org)
            if webhook or email:
                await send_monthly_report(org.id)

        logger.debug("Monthly spend reports complete — %d orgs", len(orgs))
    except Exception:
        logger.exception("Monthly spend reports job failed")
