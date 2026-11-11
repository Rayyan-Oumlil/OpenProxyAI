"""Conversations the gateway keeps (Phase 4): a thread of turns owned by one user.

Org-scoped by row-level security. Who may see a conversation *inside* an org (its owner, or a teammate when it is shared
with a team) is an application rule, because RLS here is by org only; ``app/routes/conversations.py`` enforces it and the
tests prove it for every route.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin

PRIVATE, TEAM = "private", "team"


class Conversation(UUIDPrimaryKeyMixin, Base):
	__tablename__ = "conversations"
	__table_args__ = (
		CheckConstraint("visibility IN ('private', 'team')", name="ck_conversations_visibility"),
		Index("ix_conversations_owner_updated", "owner_id", "updated_at"),
	)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
	team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
	title: Mapped[str] = mapped_column(String(200), nullable=False)
	# "team" with no team_id is a conversation whose team was deleted: nobody but the owner can read it, and the API reports it
	# as private. (A CHECK demanding a team would make deleting a team fail.)
	visibility: Mapped[str] = mapped_column(String(10), nullable=False, server_default=PRIVATE)
	tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
	updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class ConversationTurn(UUIDPrimaryKeyMixin, Base):
	"""One message. ``content`` is stored redacted. ``data_class`` is this turn's own class: what later turns' context is
	filtered by. ``seq`` orders a conversation and is unique within it, so two concurrent turns cannot both take the same slot."""

	__tablename__ = "conversation_turns"
	__table_args__ = (
		UniqueConstraint("conversation_id", "seq", name="uq_conversation_turns_seq"),
		CheckConstraint("role IN ('user', 'assistant')", name="ck_conversation_turns_role"),
	)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
	seq: Mapped[int] = mapped_column(Integer, nullable=False)
	role: Mapped[str] = mapped_column(String(10), nullable=False)
	content: Mapped[str] = mapped_column(Text, nullable=False)
	data_class: Mapped[str] = mapped_column(String(20), nullable=False)
	model: Mapped[str | None] = mapped_column(String(100), nullable=True)  # the model that wrote an assistant turn
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
