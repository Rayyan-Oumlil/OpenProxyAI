"""Request log model — ClickHouse-compatible schema for LLM request audit trail."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class RequestLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "request_logs"
    __table_args__ = (
        Index("idx_request_logs_org_created", "org_id", "created_at"),
        Index("idx_request_logs_user_created", "user_id", "created_at"),
        Index("idx_request_logs_model", "model", "created_at"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("api_keys.id")
    )
    provider_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("llm_provider_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    ttft_ms: Mapped[int | None] = mapped_column(Integer)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    request_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="request_logs")
    user: Mapped["User"] = relationship(back_populates="request_logs")

    def __repr__(self) -> str:
        return f"<RequestLog {self.request_id} model={self.model!r}>"
