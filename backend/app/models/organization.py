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
    from app.models.prompt_template import PromptTemplate
    from app.models.request_log import RequestLog
    from app.models.semantic_cache import SemanticCacheEntry
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
    # Stripe billing fields — nullable until org subscribes
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_subscription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # stripe_subscription_status mirrors Stripe values: active, past_due, canceled, paused, incomplete

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    provider_keys: Mapped[list["LLMProviderKey"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    prompt_templates: Mapped[list["PromptTemplate"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    request_logs: Mapped[list["RequestLog"]] = relationship(back_populates="organization")
    semantic_cache_entries: Mapped[list["SemanticCacheEntry"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug!r}>"
