"""Resolve MCP bundles for the gateway (design-specs A.6).

A bundle is a named set of tool patterns. A key attached to at least one bundle may only reach tools
through ``POST /v1/mcp/{slug}`` of an attached bundle; the bare ``/v1/mcp`` endpoint is refused for it,
otherwise attaching a bundle would not confine anything. Keys with no attachment behave as before.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_bundle import ApiKeyMcpBundle, McpBundle, McpBundleTool


async def key_has_bundles(db: AsyncSession, org_id: uuid.UUID, api_key_id: uuid.UUID) -> bool:
    count = await db.scalar(
        select(func.count()).select_from(ApiKeyMcpBundle).where(
            ApiKeyMcpBundle.org_id == org_id, ApiKeyMcpBundle.api_key_id == api_key_id
        )
    )
    return bool(count)


async def load_bundle_patterns(
    db: AsyncSession, org_id: uuid.UUID, api_key_id: uuid.UUID, slug: str
) -> tuple[str, ...] | None:
    """Tool patterns of the active bundle ``slug`` if ``api_key_id`` is attached to it, else None.

    Unknown, inactive and not-attached are indistinguishable to the caller on purpose (no slug probing).
    """
    bundle_id = await db.scalar(
        select(McpBundle.id)
        .join(ApiKeyMcpBundle, ApiKeyMcpBundle.bundle_id == McpBundle.id)
        .where(
            McpBundle.org_id == org_id,
            McpBundle.slug == slug,
            McpBundle.is_active.is_(True),
            ApiKeyMcpBundle.api_key_id == api_key_id,
        )
    )
    if bundle_id is None:
        return None
    rows = await db.scalars(select(McpBundleTool.tool_pattern).where(McpBundleTool.bundle_id == bundle_id))
    return tuple(sorted(rows.all()))
