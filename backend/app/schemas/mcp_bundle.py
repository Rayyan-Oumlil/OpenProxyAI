"""Schemas for virtual MCP bundles: /api/v1/mcp-bundles."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

BundleSlug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", min_length=1, max_length=40)]
ToolPattern = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_*?.\-]{1,200}$")]
MAX_BUNDLE_TOOLS = 200


class McpBundleCreateRequest(BaseModel):
	slug: BundleSlug
	name: str = Field(min_length=1, max_length=100)
	description: str | None = Field(default=None, max_length=1000)
	tools: list[ToolPattern] = Field(default_factory=list, max_length=MAX_BUNDLE_TOOLS)


class McpBundleUpdateRequest(BaseModel):
	name: str | None = Field(default=None, min_length=1, max_length=100)
	description: str | None = Field(default=None, max_length=1000)
	is_active: bool | None = None
	tools: list[ToolPattern] | None = Field(default=None, max_length=MAX_BUNDLE_TOOLS)

	@model_validator(mode="after")
	def _something_to_change(self) -> "McpBundleUpdateRequest":
		if not self.model_fields_set:
			raise ValueError("Provide at least one field to change")
		return self


class McpBundleResponse(BaseModel):
	id: UUID
	slug: str
	name: str
	description: str | None
	is_active: bool
	tools: list[str]
	api_key_ids: list[UUID]
	created_at: datetime
