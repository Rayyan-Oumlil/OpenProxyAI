"""Scheduler job: re-fetch tool lists of pinned MCP servers so drift is detected without agent traffic."""

import logging

from sqlalchemy import select

from app.config import settings
from app.database import SystemSessionLocal, org_scoped_session
from app.models.mcp_server import McpServer
from app.services.crypto_service import decrypt
from app.services.mcp_client import McpUpstreamError, call_upstream
from app.services.mcp_gateway import UpstreamServer, list_server_tools
from app.services.mcp_pinning import PIN_OFF, DbPinStore

logger = logging.getLogger(__name__)


async def sync_server(server: McpServer) -> None:
    """Fetch one server's tools and record them. Raises McpUpstreamError if the upstream fails."""
    upstream = UpstreamServer(
        id=server.id, name=server.name, url=server.url, pin_mode=server.pin_mode,
        auth_header=decrypt(server.auth_header_encrypted) if server.auth_header_encrypted else None,
    )
    live = await list_server_tools(upstream, call_upstream)
    async with org_scoped_session(server.org_id) as db:
        await DbPinStore(db, server.org_id).reconcile(upstream, live)
        await db.commit()


async def run_mcp_tool_sync() -> None:
    if not settings.MCP_TOOL_SYNC_ENABLED:
        return
    # Lists servers of every org, so it needs the system session (RLS would hide them).
    async with SystemSessionLocal() as db:
        rows = await db.scalars(select(McpServer).where(McpServer.is_active.is_(True), McpServer.pin_mode != PIN_OFF))
        servers = list(rows.all())
    for server in servers:
        try:
            await sync_server(server)
        except McpUpstreamError as exc:
            logger.warning("MCP tool sync skipped for %s: %s", server.name, exc)
        except Exception:  # noqa: BLE001 - one broken server must not stop the others
            logger.exception("MCP tool sync failed for %s", server.name)
