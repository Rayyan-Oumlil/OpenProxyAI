"""LLM provider API key model — encrypted storage with weighted rotation."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class LLMProviderKey(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "llm_provider_keys"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    key_alias: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    region: Mapped[str] = mapped_column(String(10), server_default="us", nullable=False)
    model_patterns = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="provider_keys")

    def __repr__(self) -> str:
        return f"<LLMProviderKey {self.provider!r} alias={self.key_alias!r}>"
