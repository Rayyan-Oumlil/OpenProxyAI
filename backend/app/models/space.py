"""Project spaces: a named folder a conversation can belong to.

A space is a way to find conversations, not a way to share them. Who may read a conversation is still decided by the
conversation's own owner / team / visibility (``app/routes/conversations.py``); a space lists only what the caller could
already read. A space is visible to its owner and, when it has a team, to that team's members.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class Space(UUIDPrimaryKeyMixin, Base):
	__tablename__ = "spaces"
	# A unique index on (owner_id, lower(name)) lives in the migration: one owner cannot have two spaces whose names differ only by case.
	__table_args__ = (Index("ix_spaces_org_team", "org_id", "team_id"),)

	org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
	owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
	# No team: personal to the owner. When the team is deleted the space becomes personal.
	team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
	name: Mapped[str] = mapped_column(String(100), nullable=False)
	created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
