"""Upstream MCP tool server registered by an organisation (fronted by the MCP gateway)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class McpServer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_mcp_servers_org_name"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Tool names are exposed as "<name>__<tool>", so names are restricted to [a-z0-9-].
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional "Authorization" header value sent upstream, Fernet-encrypted; never returned by the API.
    auth_header_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
