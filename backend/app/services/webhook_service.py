"""Async webhook delivery — fire-and-forget, signed payloads, delivery logging."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.webhook_delivery import WebhookDelivery
from app.utils.ssrf import is_private_or_local_ip as _is_private_or_local_ip  # noqa: F401  (re-exported for callers)
from app.utils.ssrf import resolve_safe_url as _resolve_safe_url

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds

def _is_safe_url(url: str) -> bool:
    """Thin wrapper kept for backward compatibility (schema validator, etc.)."""
    return _resolve_safe_url(url)[0]


def _build_payload(event_type: str, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "data": data,
    }


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), payload_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


async def _deliver(url: str, payload: dict, secret: str) -> tuple[str, int | None]:
    """Attempt delivery with retries. Returns (status, http_status_code).

    Resolves the hostname upfront and rejects private/local/CGN IPs,
    then makes the HTTP request to the original URL so TLS certificate
    hostname validation works correctly.
    """
    safe, _resolved_ip = _resolve_safe_url(url)
    if not safe:
        logger.warning("Blocked unsafe webhook target url=%s", url)
        return "failed", None

    body = json.dumps(payload, default=str).encode()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if secret:
        headers["X-OpenProxy-Signature"] = _sign_payload(body, secret)

    last_status: int | None = None
    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.post(url, content=body, headers=headers)
                last_status = response.status_code
                if response.is_success:
                    return "delivered", last_status
            except Exception as exc:
                logger.warning("Webhook delivery attempt %d failed: %s", attempt + 1, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_BASE_DELAY * (2 ** attempt))

    return "failed", last_status


async def dispatch_event(
    db: AsyncSession,
    org: Organization,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Dispatch a webhook event. Swallows all exceptions."""
    try:
        webhook_cfg: dict = (org.settings or {}).get("webhooks", {})
        if not webhook_cfg.get("enabled", False):
            return
        if event_type not in webhook_cfg.get("events", []):
            return

        url: str = webhook_cfg.get("url", "")
        secret: str = webhook_cfg.get("secret", "")
        if not url:
            return

        payload = _build_payload(event_type, str(org.id), data)
        status, http_status = await _deliver(url, payload, secret)

        delivery = WebhookDelivery(
            org_id=org.id,
            event_type=event_type,
            payload=payload,
            url=url,
            status=status,
            http_status=http_status,
            attempt_count=_MAX_RETRIES if status == "failed" else 1,
            last_attempted_at=datetime.now(timezone.utc),
        )
        db.add(delivery)
        await db.commit()
    except Exception:
        logger.exception("Webhook dispatch failed (org_id=%s, event=%s)", org.id, event_type)
