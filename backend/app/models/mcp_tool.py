"""Pinned MCP tool definitions (rug-pull / tool-poisoning defence) and their version history."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class McpTool(UUIDPrimaryKeyMixin, Base):
    """One tool of one upstream server.

    ``definition`` is the latest tool object the upstream advertised; ``approved_snapshot`` is the
    one an admin (or trust-on-first-use in warn mode) approved. Agents are only ever shown the snapshot.
    """

    __tablename__ = "mcp_tools"
    __table_args__ = (
        UniqueConstraint("server_id", "name", name="uq_mcp_tools_server_name"),
        CheckConstraint("status IN ('pending', 'approved', 'drifted', 'blocked')", name="ck_mcp_tools_status"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="pending")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class McpToolVersion(UUIDPrimaryKeyMixin, Base):
    """Every distinct definition a tool has ever advertised (append-only for the app role)."""

    __tablename__ = "mcp_tool_versions"
    __table_args__ = (UniqueConstraint("tool_id", "hash", name="uq_mcp_tool_versions_tool_hash"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mcp_tools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
