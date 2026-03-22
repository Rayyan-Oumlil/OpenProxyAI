"""Provider key service — rotation logic shared by API and scheduler."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_provider_key import LLMProviderKey
from app.services.admin_audit_service import log_admin_action
from app.services.crypto_service import decrypt, encrypt


async def rotate_key(
    db: AsyncSession,
    key_id: UUID,
    org_id: UUID,
    *,
    actor_id: UUID | None = None,
    actor_email: str = "admin",
    ip_address: str | None = None,
) -> bool:
    """Re-encrypt a provider key with a fresh Fernet token. Returns True if rotated."""
    key = await db.scalar(
        select(LLMProviderKey).where(
            LLMProviderKey.id == key_id,
            LLMProviderKey.org_id == org_id,
        )
    )
    if key is None:
        return False

    try:
        plaintext = decrypt(key.api_key_encrypted)
    except ValueError:
        return False

    key.api_key_encrypted = encrypt(plaintext)

    key_prefix = key.key_alias[:8] if len(key.key_alias) >= 8 else key.key_alias
    await log_admin_action(
        db,
        org_id=org_id,
        actor_id=actor_id,
        actor_email=actor_email,
        action="provider_key.rotated",
        resource_type="provider_key",
        resource_id=str(key_id),
        before={"key_prefix": key_prefix},
        after={"key_prefix": key_prefix},
        ip_address=ip_address,
    )

    return True
