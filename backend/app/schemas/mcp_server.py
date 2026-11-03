"""Schemas for registering upstream MCP servers behind the gateway."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Tools are exposed as "<name>__<tool>", so names cannot contain "__" or uppercase (see mcp_gateway).
PinMode = Literal["off", "warn", "enforce"]
ServerName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", min_length=1, max_length=40)]


class McpServerCreateRequest(BaseModel):
	name: ServerName
	url: str = Field(min_length=9, max_length=2048, description="Streamable HTTP endpoint (HTTPS, public address).")
	auth_header: str | None = Field(
		default=None, min_length=1, max_length=4096,
		description="Authorization header value sent upstream. Stored encrypted, never returned.",
	)
	pin_mode: PinMode = Field(
		default="warn",
		description="Tool pinning: off, warn (trust on first use, flag changes) or enforce (admin approval required).",
	)


class McpServerUpdateRequest(BaseModel):
	is_active: bool | None = None
	pin_mode: PinMode | None = None

	@model_validator(mode="after")
	def _something_to_change(self) -> "McpServerUpdateRequest":
		if self.is_active is None and self.pin_mode is None:
			raise ValueError("Provide is_active and/or pin_mode")
		return self


class McpServerResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	name: str
	url: str
	is_active: bool
	has_auth: bool
	pin_mode: str
	created_at: datetime

	@classmethod
	def from_model(cls, server) -> McpServerResponse:
		return cls(
			id=server.id, name=server.name, url=server.url, is_active=server.is_active,
			has_auth=bool(server.auth_header_encrypted), pin_mode=server.pin_mode, created_at=server.created_at,
		)


class McpToolResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	server_id: UUID
	name: str
	status: Literal["pending", "approved", "drifted", "blocked"]
	definition: dict[str, Any]
	approved_snapshot: dict[str, Any] | None
	current_hash: str
	approved_hash: str | None
	first_seen_at: datetime
	last_seen_at: datetime
	approved_at: datetime | None
