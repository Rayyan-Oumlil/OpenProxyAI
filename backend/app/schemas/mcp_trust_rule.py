"""Schemas for taint-tracking trust rules: /api/v1/mcp-trust-rules."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

ToolPattern = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_*?.\-]{1,200}$")]


class TrustRuleCreateRequest(BaseModel):
	tool_pattern: ToolPattern
	rule: Literal["trusted_output", "sink"]


class TrustRuleResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	tool_pattern: str
	rule: str
	created_at: datetime
