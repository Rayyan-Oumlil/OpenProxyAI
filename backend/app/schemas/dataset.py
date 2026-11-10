"""Dataset schemas (Phase 3, slice 3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.request_score import MAX_SCORE_ABS, SCORE_NAME_PATTERN

MAX_ITEMS_PER_DATASET = 10_000
MAX_IMPORT = 1_000
MAX_TEXT_CHARS = 50_000

DatasetName = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]


class DatasetCreate(BaseModel):
	model_config = ConfigDict(extra="forbid")

	name: DatasetName
	description: str | None = Field(default=None, max_length=500)


class DatasetResponse(BaseModel):
	id: uuid.UUID
	name: str
	description: str | None
	item_count: int
	created_at: datetime


class ItemMessage(BaseModel):
	model_config = ConfigDict(extra="forbid")

	role: Literal["system", "user", "assistant"]
	content: str = Field(max_length=MAX_TEXT_CHARS)  # text only; tool calls and images are not dataset material


class ItemCreate(BaseModel):
	"""An item added by hand: the prompt, and optionally the answer it should produce."""

	model_config = ConfigDict(extra="forbid")

	messages: list[ItemMessage] = Field(min_length=1, max_length=50)
	expected: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)


class ItemResponse(BaseModel):
	id: uuid.UUID
	request_id: uuid.UUID | None
	messages: list
	output: str | None
	expected: str | None
	created_at: datetime


class ImportRequest(BaseModel):
	"""Which captured requests to copy into the dataset. Rows the PII detector touched are never imported."""

	model_config = ConfigDict(extra="forbid")

	model: str | None = Field(default=None, max_length=100)
	since: datetime | None = None
	until: datetime | None = None
	score_name: str | None = Field(default=None, pattern=SCORE_NAME_PATTERN)
	min_score: float | None = Field(default=None, ge=-MAX_SCORE_ABS, le=MAX_SCORE_ABS)
	max_score: float | None = Field(default=None, ge=-MAX_SCORE_ABS, le=MAX_SCORE_ABS)
	limit: int = Field(default=100, ge=1, le=MAX_IMPORT)
	order: Literal["latest", "random"] = "latest"

	@model_validator(mode="after")
	def consistent_filters(self) -> "ImportRequest":
		if (self.min_score is not None or self.max_score is not None) and self.score_name is None:
			raise ValueError("min_score and max_score need a score_name")
		if self.min_score is not None and self.max_score is not None and self.min_score > self.max_score:
			raise ValueError("min_score is above max_score")
		if self.since is not None and self.until is not None and self.since > self.until:
			raise ValueError("since is after until")
		return self


class ImportResponse(BaseModel):
	imported: int
	skipped_redacted: int  # matched the filters but PII was found in them
	skipped_duplicate: int  # matched the filters but are already in this dataset
	stopped_at_capacity: bool  # the dataset reached its item limit before every match was copied
