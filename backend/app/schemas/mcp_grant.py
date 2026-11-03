"""Schemas for per-tool grants: /api/v1/mcp-grants."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

ToolPattern = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_*?.\-]{1,200}$")]
ROLES = ("admin", "developer", "viewer")


class McpGrantCreateRequest(BaseModel):
	subject_type: Literal["role", "team", "user", "api_key"]
	subject_id: str
	tool_pattern: ToolPattern
	effect: Literal["allow", "deny"]

	@model_validator(mode="after")
	def _subject_is_well_formed(self) -> McpGrantCreateRequest:
		if self.subject_type == "role":
			if self.subject_id not in ROLES:
				raise ValueError(f"role must be one of {', '.join(ROLES)}")
		else:
			try:
				UUID(self.subject_id)
			except ValueError as exc:
				raise ValueError(f"{self.subject_type} subject_id must be a UUID") from exc
		return self


class McpGrantResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	subject_type: str
	subject_id: str
	tool_pattern: str
	effect: str
	created_at: datetime
