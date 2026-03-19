"""Admin action audit logging — SOC 2 CC6 compliance."""
from __future__ import annotations
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin_audit_log import AdminAuditLog

logger = logging.getLogger(__name__)


async def log_admin_action(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    actor_email: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip_address: str | None = None,
) -> AdminAuditLog:
    """Add an audit log entry to the current session.

    Does NOT commit. The caller commits atomically with their own changes.
    """
    entry = AdminAuditLog(
        org_id=org_id,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before,
        after=after,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry


# --- Serialization allowlists (no secrets ever logged) ---

def serialize_provider_key(key) -> dict:
    return {
        "id": str(key.id),
        "alias": key.key_alias,
        "provider": key.provider,
        "weight": key.weight,
        "is_active": key.is_active,
        "region": key.region,
        "model_patterns": key.model_patterns,
    }


def serialize_webhook_config(cfg: dict) -> dict:
    """Exclude secret from webhook config snapshots."""
    return {
        "url": cfg.get("url"),
        "events": cfg.get("events"),
        "enabled": cfg.get("enabled"),
    }


def serialize_team(team) -> dict:
    return {
        "id": str(team.id),
        "name": team.name,
        "budget_monthly_usd": str(team.budget_monthly_usd) if team.budget_monthly_usd else None,
    }


def serialize_user(user) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "budget_daily_usd": str(user.budget_daily_usd) if user.budget_daily_usd else None,
        "budget_monthly_usd": str(user.budget_monthly_usd) if user.budget_monthly_usd else None,
    }


def serialize_org(org) -> dict:
    return {
        "name": org.name,
        "plan": org.plan,
        "budget_monthly_usd": str(org.budget_monthly_usd) if org.budget_monthly_usd else None,
        "data_region": org.data_region,
    }


def get_ip(request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
