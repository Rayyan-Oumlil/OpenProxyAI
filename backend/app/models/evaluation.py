"""Evaluators, eval runs and their per-item results (Phase 3, slice 4). All org-scoped by RLS."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class Evaluator(UUIDPrimaryKeyMixin, Base):
	__tablename__ = "evaluators"
	__table_args__ = (UniqueConstraint("org_id", "name", name="uq_evaluators_org_name"),)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	name: Mapped[str] = mapped_column(String(100), nullable=False)
	type: Mapped[str] = mapped_column(String(20), nullable=False)  # exact | regex | llm_judge
	config: Mapped[dict] = mapped_column(JSONB, nullable=False)
	created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class EvalRun(UUIDPrimaryKeyMixin, Base):
	"""One candidate model scored on one dataset by one evaluator.

	``status``: queued, running, completed, failed, cancelled or budget_exceeded. The evaluator's config is copied into
	``evaluator_snapshot`` so a run stays interpretable after the evaluator is edited or deleted.
	"""

	__tablename__ = "eval_runs"
	__table_args__ = (Index("ix_eval_runs_org_created", "org_id", "created_at"),)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	dataset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
	evaluator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evaluators.id", ondelete="SET NULL"), nullable=True)
	evaluator_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
	prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True)
	candidate_model: Mapped[str] = mapped_column(String(100), nullable=False)
	system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
	status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
	total_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
	completed_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
	failed_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")  # could not be scored
	passed_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
	score_sum: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
	cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
	max_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
	error: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
	started_at: Mapped[datetime | None] = mapped_column(nullable=True)
	finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class EvalRunItem(UUIDPrimaryKeyMixin, Base):
	__tablename__ = "eval_run_items"
	__table_args__ = (
		UniqueConstraint("run_id", "dataset_item_id", name="uq_eval_run_items_run_item"),
		Index("ix_eval_run_items_run_id", "run_id"),
	)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False)
	dataset_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dataset_items.id", ondelete="SET NULL"), nullable=True)
	output: Mapped[str | None] = mapped_column(Text, nullable=True)
	score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
	passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
	reason: Mapped[str | None] = mapped_column(Text, nullable=True)
	error: Mapped[str | None] = mapped_column(Text, nullable=True)
	cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
	latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
