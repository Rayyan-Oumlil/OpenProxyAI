"""Schemas for registering upstream MCP servers behind the gateway."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Tools are exposed as "<name>__<tool>", so names cannot contain "__" or uppercase (see mcp_gateway).
ServerName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", min_length=1, max_length=40)]


class McpServerCreateRequest(BaseModel):
	name: ServerName
	url: str = Field(min_length=9, max_length=2048, description="Streamable HTTP endpoint (HTTPS, public address).")
	auth_header: str | None = Field(
		default=None, min_length=1, max_length=4096,
		description="Authorization header value sent upstream. Stored encrypted, never returned.",
	)


class McpServerUpdateRequest(BaseModel):
	is_active: bool


class McpServerResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	name: str
	url: str
	is_active: bool
	has_auth: bool
	created_at: datetime

	@classmethod
	def from_model(cls, server) -> McpServerResponse:
		return cls(
			id=server.id, name=server.name, url=server.url, is_active=server.is_active,
			has_auth=bool(server.auth_header_encrypted), created_at=server.created_at,
		)
