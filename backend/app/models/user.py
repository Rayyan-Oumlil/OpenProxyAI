"""User model with role-based access (admin, developer, viewer)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.organization import Organization
    from app.models.request_log import RequestLog


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'developer', 'viewer')",
            name="ck_users_role_valid",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="developer")
    budget_daily_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    budget_monthly_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column()
    sso_sub: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sso_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sso_connections.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="users")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    request_logs: Mapped[list["RequestLog"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email!r}>"
