"""Trust rules for taint tracking: which tools return trusted output, and which tools are sinks."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class ToolTrustRule(UUIDPrimaryKeyMixin, Base):
    """One fnmatch pattern over the namespaced tool name (``<server>__<tool>``).

    ``trusted_output``  the tool's results come from a source the org trusts, so they do not taint a session
    ``sink``            the tool has side effects (send, write, delete, pay); it must not run in a tainted
                        or session-less context

    Everything not matched by a ``trusted_output`` rule is treated as untrusted (secure by default).
    """

    __tablename__ = "tool_trust_rules"
    __table_args__ = (
        UniqueConstraint("org_id", "tool_pattern", "rule", name="uq_tool_trust_rules_rule"),
        CheckConstraint("rule IN ('trusted_output', 'sink')", name="ck_tool_trust_rules_rule"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    rule: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
