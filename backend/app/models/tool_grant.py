"""Per-tool grants: who may (allow) or may not (deny) use which MCP tools."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class ToolGrant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tool_grants"
    __table_args__ = (
        UniqueConstraint("org_id", "subject_type", "subject_id", "tool_pattern", "effect", name="uq_tool_grants_rule"),
        CheckConstraint("subject_type IN ('role', 'team', 'user', 'api_key')", name="ck_tool_grants_subject_type"),
        CheckConstraint("effect IN ('allow', 'deny')", name="ck_tool_grants_effect"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # A role name ('admin', 'developer', 'viewer') or the UUID of a team, user or API key.
    subject_type: Mapped[str] = mapped_column(String(10), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # fnmatch glob over the namespaced tool name, e.g. "github__*" or "jira__create_issue".
    tool_pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    effect: Mapped[str] = mapped_column(String(5), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
