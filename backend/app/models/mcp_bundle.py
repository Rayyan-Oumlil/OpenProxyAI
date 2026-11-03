"""Virtual MCP bundles: a named set of tool patterns, attached to API keys, served at /v1/mcp/{slug}."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class McpBundle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mcp_bundles"
    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_mcp_bundles_org_slug"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 40", name="ck_mcp_bundles_slug"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class McpBundleTool(UUIDPrimaryKeyMixin, Base):
    """One fnmatch pattern over the namespaced tool name (``<server>__<tool>``)."""

    __tablename__ = "mcp_bundle_tools"
    __table_args__ = (UniqueConstraint("bundle_id", "tool_pattern", name="uq_mcp_bundle_tools_pattern"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bundle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mcp_bundles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_pattern: Mapped[str] = mapped_column(String(200), nullable=False)


class ApiKeyMcpBundle(Base):
    """Attaches an API key to a bundle. A key with any attachment is confined to its bundles."""

    __tablename__ = "api_key_mcp_bundles"

    api_key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("api_keys.id", ondelete="CASCADE"), primary_key=True)
    bundle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mcp_bundles.id", ondelete="CASCADE"), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
