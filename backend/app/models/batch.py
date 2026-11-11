"""Files and batch jobs (Phase 5, slice 5.6). Org-scoped by RLS."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class BatchFile(UUIDPrimaryKeyMixin, Base):
	"""An uploaded input file or a finished job's output. Holds the real text (a batch must send what the user wrote), so it expires."""

	__tablename__ = "batch_files"
	__table_args__ = (
		CheckConstraint("purpose IN ('batch', 'output')", name="ck_batch_files_purpose"),
		CheckConstraint("size_bytes >= 0 AND size_bytes <= 16777216", name="ck_batch_files_size"),
	)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
	filename: Mapped[str] = mapped_column(String(255), nullable=False)
	purpose: Mapped[str] = mapped_column(String(10), nullable=False)
	size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
	line_count: Mapped[int] = mapped_column(Integer, nullable=False)
	content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
	expires_at: Mapped[datetime] = mapped_column(nullable=False)


class BatchJob(UUIDPrimaryKeyMixin, Base):
	__tablename__ = "batch_jobs"
	__table_args__ = (
		CheckConstraint(
			"status IN ('validating', 'in_progress', 'completed', 'failed', 'cancelled', 'budget_exceeded')", name="ck_batch_jobs_status"
		),
	)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
	input_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("batch_files.id", ondelete="SET NULL"), nullable=True)
	output_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("batch_files.id", ondelete="SET NULL"), nullable=True)
	endpoint: Mapped[str] = mapped_column(String(40), nullable=False)
	status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="validating")
	total: Mapped[int] = mapped_column(Integer, nullable=False)
	completed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
	failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
	cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
	max_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
	error: Mapped[str | None] = mapped_column(Text, nullable=True)
	extra: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
	started_at: Mapped[datetime | None] = mapped_column(nullable=True)
	finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class BatchResult(UUIDPrimaryKeyMixin, Base):
	"""One finished line, held until the job ends and the output file is assembled from them."""

	__tablename__ = "batch_results"
	__table_args__ = (UniqueConstraint("job_id", "idx", name="uq_batch_results_job_idx"),)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False)
	idx: Mapped[int] = mapped_column(Integer, nullable=False)
	custom_id: Mapped[str] = mapped_column(String(64), nullable=False)
	status_code: Mapped[int] = mapped_column(Integer, nullable=False)
	body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
	error: Mapped[str | None] = mapped_column(Text, nullable=True)
