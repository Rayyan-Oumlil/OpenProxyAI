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


MODEL_PATTERN = r"^[A-Za-z0-9._-]+/[A-Za-z0-9._:/@-]+$"  # "provider/name"; capability routes ("cap:...") are not for conversations
MAX_MESSAGE_CHARS = 20_000


class TurnRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
	model: str = Field(pattern=MODEL_PATTERN, max_length=100)
	data_class: Literal["public", "internal", "confidential", "secret"] | None = Field(
		default=None, description="Assert a class for this message. It can only raise the class, never lower it."
	)
	system_prompt: str | None = Field(default=None, max_length=4_000)
	temperature: float | None = Field(default=None, ge=0, le=2)
	max_tokens: int | None = Field(default=None, ge=1, le=32_000)
	max_context_tokens: int | None = Field(default=None, ge=1, le=200_000)

	@field_validator("content")
	@classmethod
	def _not_blank(cls, value: str) -> str:
		if not value.strip():
			raise ValueError("content cannot be blank")
		return value


class WithheldTurn(BaseModel):
	turn_id: uuid.UUID
	seq: int
	reason: Literal["above_clearance", "over_budget"]


class ContextSummary(BaseModel):
	package_id: uuid.UUID
	model: str
	data_class: str
	routing_mode: str
	included_turn_ids: list[uuid.UUID]
	withheld: list[WithheldTurn]
	estimated_tokens: int
	payload_sha256: str
	outcome: str
	created_at: datetime


class TurnExchange(BaseModel):
	user_turn: TurnResponse
	assistant_turn: TurnResponse
	context: ContextSummary
	prompt_tokens: int
	completion_tokens: int
	cost_usd: str


class TeamChoice(BaseModel):
	id: uuid.UUID
	name: str


class ModelChoice(BaseModel):
	model_id: str
	max_data_class: str  # the highest class this model may receive: the lower of its registry entry's and its key's
