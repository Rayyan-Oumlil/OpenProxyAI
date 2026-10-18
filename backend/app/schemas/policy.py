"""Policy configuration schemas — request/response for the policy config API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, StringConstraints

# fnmatch pattern on a namespaced MCP tool name, e.g. "github__*".
ToolPattern = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]


class PolicyConfigRequest(BaseModel):
	"""Partial update — only provided fields are changed."""

	enforcement_mode: Literal["off", "log_only", "enforce"] | None = None
	allowed_models: list[str] | None = None
	blocked_keywords: list[str] | None = None
	pii_detection_enabled: bool | None = None
	pii_entities: list[str] | None = None
	model_rate_limits: Optional[dict] = None
	per_team_limits: Optional[dict] = None  # {"rpm": 60, "tpm": 50000} for requests with team_id
	prompt_injection_detection_enabled: bool | None = None
	response_guardrails_enabled: bool | None = None
	response_pii_redact: bool | None = None
	mcp_allowed_tools: list[ToolPattern] | None = None
	mcp_blocked_tools: list[ToolPattern] | None = None


class PolicyConfigResponse(BaseModel):
	enforcement_mode: str
	allowed_models: list[str]
	blocked_keywords: list[str]
	pii_detection_enabled: bool
	pii_entities: list[str]
	model_rate_limits: dict
	per_team_limits: dict = {}
	updated_at: datetime | None
	prompt_injection_detection_enabled: bool
	response_guardrails_enabled: bool
	response_pii_redact: bool
	mcp_allowed_tools: list[str] = []
	mcp_blocked_tools: list[str] = []


class ApplyTemplateRequest(BaseModel):
	template: str  # Validated in route to return 400 for unknown values


class TemplateListItem(BaseModel):
	name: str
	description: str
	configures: list[str]
