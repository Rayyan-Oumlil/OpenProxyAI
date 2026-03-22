"""Request score model — quality scores per request for experiment evaluation."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin

# No direct FK to request_logs (request_id is gateway UUID, not request_logs.id)
# Org scoping via request_logs join when querying


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
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

	def __repr__(self) -> str:
		return f"<RequestScore {self.score_name}={self.value} request={self.request_id}>"
