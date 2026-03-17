"""Organization (tenant) model — multi-tenant isolation boundary."""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.llm_provider_key import LLMProviderKey
    from app.models.request_log import RequestLog
    from app.models.user import User


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, server_default="free")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    budget_monthly_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    data_region: Mapped[str] = mapped_column(String(50), nullable=True, default="us")

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    provider_keys: Mapped[list["LLMProviderKey"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    request_logs: Mapped[list["RequestLog"]] = relationship(back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization {self.slug!r}>"
