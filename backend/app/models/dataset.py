"""Evaluation datasets: named, curated sets of prompts (and optionally reference answers) an org tests changes against."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class Dataset(UUIDPrimaryKeyMixin, Base):
	"""Org-scoped by RLS. Unique name per org."""

	__tablename__ = "datasets"
	__table_args__ = (UniqueConstraint("org_id", "name", name="uq_datasets_org_name"),)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	name: Mapped[str] = mapped_column(String(100), nullable=False)
	description: Mapped[str | None] = mapped_column(String(500), nullable=True)
	created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class DatasetItem(UUIDPrimaryKeyMixin, Base):
	"""One prompt to test with. ``request_id`` is set for items imported from captured traffic, which makes an import
	idempotent; it is null for items added by hand.

	An item is a copy: it does not expire with the captured payload it came from, and goes only when an admin deletes
	the item or its dataset.
	"""

	__tablename__ = "dataset_items"
	__table_args__ = (
		UniqueConstraint("dataset_id", "request_id", name="uq_dataset_items_dataset_request"),  # nulls are distinct in Postgres
		Index("ix_dataset_items_dataset_id", "dataset_id"),
	)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
	request_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
	messages: Mapped[list] = mapped_column(JSONB, nullable=False)
	output: Mapped[str | None] = mapped_column(Text, nullable=True)  # the answer the gateway delivered when it was captured
	expected: Mapped[str | None] = mapped_column(Text, nullable=True)  # a reference answer, for exact and regex evaluators
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
