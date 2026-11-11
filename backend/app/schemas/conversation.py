"""Conversation schemas (Phase 4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

MAX_TAGS = 10
MAX_PER_USER = 500  # conversations one user may keep; a ceiling against runaway scripts, far above human use

Title = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Tag = Annotated[str, StringConstraints(min_length=1, max_length=30, strip_whitespace=True)]
Visibility = Literal["private", "team"]


def _clean_tags(tags: list[str]) -> list[str]:
	"""Lower-cased, de-duplicated, in the order given."""
	seen: dict[str, None] = {}
	for tag in tags:
		seen.setdefault(tag.lower(), None)
	return list(seen)


class ConversationCreate(BaseModel):
	model_config = ConfigDict(extra="forbid")

	title: Title
	visibility: Visibility = "private"
	team_id: uuid.UUID | None = None
	tags: list[Tag] = Field(default_factory=list, max_length=MAX_TAGS)

	@field_validator("tags")
	@classmethod
	def _tags(cls, value: list[str]) -> list[str]:
		return _clean_tags(value)

	@model_validator(mode="after")
	def _team_matches_visibility(self) -> "ConversationCreate":
		if self.visibility == "team" and self.team_id is None:
			raise ValueError("team_id is required when visibility is 'team'")
		if self.visibility == "private" and self.team_id is not None:
			raise ValueError("team_id is only for a conversation shared with a team")
		return self


class ConversationUpdate(BaseModel):
	"""Only what is sent changes. Going private clears the team; sharing needs a team (sent now, or already set)."""

	model_config = ConfigDict(extra="forbid")

	title: Title | None = None
	visibility: Visibility | None = None
	team_id: uuid.UUID | None = None
	tags: list[Tag] | None = Field(default=None, max_length=MAX_TAGS)

	@field_validator("title", "visibility", "tags", mode="before")
	@classmethod
	def _not_null(cls, value):
		if value is None:
			raise ValueError("cannot be null; omit the field to leave it unchanged")
		return value

	@field_validator("tags")
	@classmethod
	def _tags(cls, value: list[str] | None) -> list[str] | None:
		return None if value is None else _clean_tags(value)


class ConversationResponse(BaseModel):
	id: uuid.UUID
	title: str
	visibility: str
	team_id: uuid.UUID | None
	tags: list[str]
	owner_id: uuid.UUID
	owner_email: str | None
	is_owner: bool
	turn_count: int
	created_at: datetime
	updated_at: datetime


class TurnResponse(BaseModel):
	id: uuid.UUID
	seq: int
	role: str
	content: str
	data_class: str
	model: str | None
	created_at: datetime
