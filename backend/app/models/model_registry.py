"""Model registry: what each model is, where it runs, and the most sensitive data it may receive.

Phase 2 routing (slice S4) decides from this table. Until then it is administration only: nothing reads it on the
request path.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class ModelRegistryEntry(UUIDPrimaryKeyMixin, Base):
    """One model an org has vetted. ``model_id`` is ``provider/name`` exactly as clients send it.

    The endpoint comes from the linked provider key (its ``api_base``); an entry whose key was deleted keeps its
    governance data but has no key, and is not routable until an admin attaches another.
    """

    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("org_id", "model_id", name="uq_model_registry_org_model"),
        # Names the org too, so the database refuses a link to another org's key (row-level security does not apply to
        # foreign keys). Deleting the key detaches the entry without touching its org_id (PostgreSQL 15+).
        ForeignKeyConstraint(
            ["org_id", "provider_key_id"], ["llm_provider_keys.org_id", "llm_provider_keys.id"],
            ondelete="SET NULL (provider_key_id)", name="fk_model_registry_key_same_org",
        ),
        CheckConstraint("max_data_class IN ('public', 'internal', 'confidential', 'secret')", name="ck_model_registry_data_class"),
        CheckConstraint("risk_rating IN ('low', 'medium', 'high')", name="ck_model_registry_risk"),
        CheckConstraint("cost_tier IS NULL OR cost_tier IN ('low', 'medium', 'high')", name="ck_model_registry_cost_tier"),
        CheckConstraint("retention_days IS NULL OR retention_days >= 0", name="ck_model_registry_retention"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_key_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    max_data_class: Mapped[str] = mapped_column(String(20), nullable=False, server_default="internal")
    regions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    risk_rating: Mapped[str] = mapped_column(String(10), nullable=False, server_default="medium")
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trains_on_data: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cost_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)
