"""Request score model — quality scores per request for experiment evaluation."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin

# No direct FK to request_logs (request_id is gateway UUID, not request_logs.id)
# Org-scoped by RLS (v3q4r5s6t7u8); unique on (org_id, request_id, score_name)


class RequestScore(UUIDPrimaryKeyMixin, Base):
	__tablename__ = "request_scores"

	request_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
	org_id: Mapped[uuid.UUID] = mapped_column(
		ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
	)
	experiment_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True
	)
	variant_id: Mapped[uuid.UUID | None] = mapped_column(
		ForeignKey("experiment_variants.id", ondelete="CASCADE"), nullable=True
	)
	score_name: Mapped[str] = mapped_column(String(100), nullable=False)
	value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
	# Where the score came from: "console" (a signed-in user), "api" (an application with an API key); later "evaluator".
	source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="console")
	comment: Mapped[str | None] = mapped_column(Text, nullable=True)  # PII-redacted before it is stored
	user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

	def __repr__(self) -> str:
		return f"<RequestScore {self.score_name}={self.value} request={self.request_id}>"
