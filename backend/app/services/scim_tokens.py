"""SCIM bearer tokens: create, rotate, revoke, and resolve a presented token to its org.

The token is 256 bits of randomness, shown once, stored only as a SHA-256 (the same scheme as API keys: a slow hash
adds nothing for a secret that cannot be guessed). A SCIM token is not an API key: it is rejected by the proxy and the
management API, and it can only call /scim/v2.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_session_org_id
from app.models.scim_token import ScimToken

TOKEN_PREFIX = "scim_"
_PREFIX_SHOWN = 12


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


async def get_live_token(db: AsyncSession, org_id: uuid.UUID) -> ScimToken | None:
    return await db.scalar(select(ScimToken).where(ScimToken.org_id == org_id, ScimToken.revoked_at.is_(None)))


async def revoke_live_token(db: AsyncSession, org_id: uuid.UUID) -> ScimToken | None:
    """Mark the org's live token revoked and drop its lookup row, so it stops authenticating at once. Does not commit."""
    live = await get_live_token(db, org_id)
    if live is None:
        return None
    live.revoked_at = _now()
    await db.execute(delete_lookup(live.token_hash))
    return live


def delete_lookup(token_hash: str):
    return text("DELETE FROM scim_token_lookup WHERE token_hash = :h").bindparams(h=token_hash)


async def issue_token(db: AsyncSession, org_id: uuid.UUID, created_by: uuid.UUID | None) -> tuple[ScimToken, str, bool]:
    """Create a token, replacing any live one. Returns (row, plaintext, rotated). Does not commit."""
    rotated = await revoke_live_token(db, org_id) is not None
    # The unique "one live token per org" index needs the revoked row's flag to be written first.
    await db.flush()
    plaintext = new_token()
    digest = hash_token(plaintext)
    row = ScimToken(org_id=org_id, token_prefix=plaintext[:_PREFIX_SHOWN], token_hash=digest, created_by=created_by)
    db.add(row)
    await db.flush()
    await db.execute(
        text("INSERT INTO scim_token_lookup (token_hash, org_id, token_id) VALUES (:h, :o, :t)"),
        {"h": digest, "o": org_id, "t": row.id},
    )
    return row, plaintext, rotated


async def resolve_token(db: AsyncSession, presented: str) -> ScimToken | None:
    """Return the live token row for a presented bearer value, with the session scoped to its org; None if invalid."""
    if not presented.startswith(TOKEN_PREFIX):
        return None
    digest = hash_token(presented)
    found = (await db.execute(text("SELECT org_id, token_id FROM scim_token_lookup WHERE token_hash = :h"), {"h": digest})).mappings().first()
    if found is None:
        return None
    org_id = found["org_id"] if isinstance(found["org_id"], uuid.UUID) else uuid.UUID(str(found["org_id"]))
    await set_session_org_id(db, org_id)
    row = await db.scalar(select(ScimToken).where(ScimToken.id == found["token_id"]))
    if row is None or row.revoked_at is not None or row.org_id != org_id:
        return None
    if not hmac.compare_digest(row.token_hash, digest):
        return None
    return row
