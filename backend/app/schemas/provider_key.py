"""LLM provider key schemas — CRUD request/response (key values always masked)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProviderKeyCreateRequest(BaseModel):
	provider: str = Field(min_length=1, max_length=50)
	key_alias: str = Field(min_length=1, max_length=100)
	api_key: str = Field(min_length=8, description="Raw API key — stored encrypted, never returned.")
	weight: int = Field(default=1, ge=1, le=100)


class ProviderKeyUpdateRequest(BaseModel):
	"""Partial update — only provided fields are changed."""

	key_alias: str | None = Field(default=None, min_length=1, max_length=100)
	weight: int | None = Field(default=None, ge=1, le=100)
	is_active: bool | None = None


class ProviderKeyResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	provider: str
	key_alias: str
	key_prefix: str  # first 8 chars + "…" — raw key is never returned
	weight: int
	is_active: bool
	created_at: datetime
