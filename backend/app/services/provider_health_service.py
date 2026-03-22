"""Provider health check service — pings provider keys and marks unhealthy after N failures."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, set_session_org_id
from app.models.llm_provider_key import LLMProviderKey
from app.models.organization import Organization
from app.services.crypto_service import decrypt

logger = logging.getLogger(__name__)

# Minimal health check requests (cheapest models, 1 token)
OPENAI_HEALTH_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_HEALTH_URL = "https://api.anthropic.com/v1/messages"
HEALTH_TIMEOUT = 5.0


async def _ping_openai(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT) as client:
            r = await client.post(
                OPENAI_HEALTH_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "x"}],
                    "max_tokens": 1,
                },
            )
            return r.status_code in (200, 201)
    except Exception as e:
        logger.debug("OpenAI health check failed: %s", e)
        return False


async def _ping_anthropic(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT) as client:
            r = await client.post(
                ANTHROPIC_HEALTH_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "x"}],
                },
            )
            return r.status_code in (200, 201)
    except Exception as e:
        logger.debug("Anthropic health check failed: %s", e)
        return False


async def _ping_provider(provider: str, api_key: str) -> bool:
    if provider == "openai":
        return await _ping_openai(api_key)
    if provider == "anthropic":
        return await _ping_anthropic(api_key)
    # Azure and others — skip or extend later
    logger.debug("Health check not implemented for provider %s", provider)
    return True  # Assume healthy if unsupported


async def run_provider_health_check() -> None:
    """Scheduler job: ping all active provider keys, update health_status."""
    if not getattr(settings, "PROVIDER_HEALTH_CHECK_ENABLED", False):
        return

    threshold = getattr(settings, "PROVIDER_HEALTH_FAILURE_THRESHOLD", 3)

    try:
        async with AsyncSessionLocal() as db:
            result = await db.scalars(
                select(LLMProviderKey).where(
                    LLMProviderKey.is_active.is_(True),
                    LLMProviderKey.weight > 0,
                )
            )
            keys = list(result.all())

        for key in keys:
            try:
                plaintext = decrypt(key.api_key_encrypted)
            except Exception:
                plaintext = ""
            if not plaintext:
                continue

            ok = await _ping_provider(key.provider, plaintext)
            now = datetime.now(UTC)

            async with AsyncSessionLocal() as db:
                await set_session_org_id(db, key.org_id)
                k = await db.get(LLMProviderKey, key.id)
                if k is None:
                    continue
                if ok:
                    k.consecutive_failures = 0
                    k.health_status = "healthy"
                    k.last_health_check_at = now
                else:
                    k.consecutive_failures = (k.consecutive_failures or 0) + 1
                    k.last_health_check_at = now
                    if k.consecutive_failures >= threshold:
                        k.health_status = "unhealthy"
                await db.commit()

        logger.debug("Provider health check complete — %d keys", len(keys))
    except Exception:
        logger.exception("Provider health check job failed")
