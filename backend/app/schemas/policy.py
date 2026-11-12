"""Policy configuration schemas — request/response for the policy config API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.services.data_class import DataClass

# fnmatch pattern on a namespaced MCP tool name, e.g. "github__*".
ToolPattern = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]

# Name of a detected kind of PII, e.g. "ssn" or "US_SSN".
EntityName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_]{1,50}$")]


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
	default_data_class: DataClass | None = None
	data_class_map: dict[EntityName, DataClass] | None = None
	routing_mode: Literal["off", "log_only", "enforce"] | None = None
	max_risk_rating: Literal["low", "medium", "high"] | None = None
	routing_quality_signal: Literal["off", "feedback"] | None = None
	payload_capture_sample_rate: float | None = Field(default=None, ge=0, le=1)
	prompt_promotion_gate: bool | None = None
	prompt_gate_min_pass_rate: float | None = Field(default=None, gt=0, le=1)
	prompt_gate_min_items: int | None = Field(default=None, ge=1, le=100_000)
	conversations_enabled: bool | None = None
	allow_provider_response_state: bool | None = None

	@field_validator("default_data_class", "routing_mode", "max_risk_rating", "routing_quality_signal", "payload_capture_sample_rate", "prompt_promotion_gate", "prompt_gate_min_pass_rate", "prompt_gate_min_items", "conversations_enabled", "allow_provider_response_state", mode="before")
	@classmethod
	def _not_null(cls, value):
		if value is None:
			raise ValueError("cannot be null; omit the field to leave it unchanged")
		return value

	@field_validator("data_class_map")
	@classmethod
	def _map_is_bounded(cls, value):
		if value is not None and len(value) > 50:
			raise ValueError("at most 50 entries")
		return value


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
	default_data_class: str = "internal"
	data_class_map: dict[str, str] = {}
	routing_mode: str = "off"
	max_risk_rating: str = "high"
	routing_quality_signal: str = "off"
	payload_capture_sample_rate: float = 0.0
	prompt_promotion_gate: bool = False
	prompt_gate_min_pass_rate: float = 0.8
	prompt_gate_min_items: int = 10
	conversations_enabled: bool = False
	allow_provider_response_state: bool = False


class ApplyTemplateRequest(BaseModel):
	template: str  # Validated in route to return 400 for unknown values


class TemplateListItem(BaseModel):
	name: str
	description: str
	configures: list[str]
