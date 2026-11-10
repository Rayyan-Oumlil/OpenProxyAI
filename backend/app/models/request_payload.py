"""Request payload model — the redacted prompt and answer of a sampled request, kept only for evaluation."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class RequestPayload(UUIDPrimaryKeyMixin, Base):
	"""Written in the background, after PII redaction, only when the org opted in and sampled this request.

	Org-scoped by RLS. ``redacted`` records that the detector replaced something, so datasets (slice 3) can refuse the row.
	Deleted once ``expires_at`` passes, which follows the plan's audit retention.
	"""

	__tablename__ = "request_payloads"
	__table_args__ = (
		UniqueConstraint("org_id", "request_id", name="uq_request_payloads_org_request"),
		Index("ix_request_payloads_expires_at", "expires_at"),
	)

	request_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	messages: Mapped[list] = mapped_column(JSONB, nullable=False)
	output: Mapped[str] = mapped_column(Text, nullable=False)
	redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
	expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

	def __repr__(self) -> str:
		return f"<RequestPayload request={self.request_id} redacted={self.redacted}>"
