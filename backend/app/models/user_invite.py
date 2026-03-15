"""UserInvite model — tracks pending and accepted invitation tokens."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class UserInvite(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_invites"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'developer', 'viewer')",
            name="ck_user_invites_role_valid",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="developer")
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(foreign_keys=[org_id])
    inviter: Mapped["User | None"] = relationship(foreign_keys=[invited_by])

    def __repr__(self) -> str:
        return f"<UserInvite {self.email!r} org={self.org_id}>"
