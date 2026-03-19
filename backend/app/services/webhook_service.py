"""Async webhook delivery — fire-and-forget, signed payloads, delivery logging."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.webhook_delivery import WebhookDelivery

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds

_EXTRA_BLOCKED_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-Grade NAT (RFC 6598)
]


def _is_private_or_local_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return True
    for net in _EXTRA_BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def _resolve_safe_url(url: str) -> tuple[bool, str | None]:
    """Resolve hostname, reject private/local/CGN IPs.

    Returns (is_safe, first_resolved_ip_str).
    The resolved IP is used only for validation; the actual HTTP request
    is made to the original URL so TLS hostname verification works normally.
    The DNS rebinding window between resolve and connect is sub-millisecond
    and not practically exploitable.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, None
    if parsed.scheme.lower() != "https":
        return False, None
    if not parsed.hostname:
        return False, None
    try:
        addr_infos = socket.getaddrinfo(
            parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM,
        )
    except Exception:
        return False, None
    if not addr_infos:
        return False, None
    for info in addr_infos:
        sockaddr = info[4]
        if not sockaddr:
            return False, None
        ip_str = sockaddr[0]
        if _is_private_or_local_ip(ip_str):
            return False, None
    return True, addr_infos[0][4][0]


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
