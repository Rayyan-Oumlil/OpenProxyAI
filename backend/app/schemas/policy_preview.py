"""Schemas for the policy preview: /api/v1/policy/preview."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import Message
from app.services.data_class import DataClass


class PolicyPreviewRequest(BaseModel):
	"""A request as a client would send it. Nothing is sent anywhere and nothing is stored."""

	model: str = Field(min_length=1, max_length=200, description="provider/name, or cap:NAME to route by capability")
	messages: list[Message] = Field(min_length=1)
	data_class: DataClass | None = Field(default=None, description="What a caller would assert in x-openproxy-data-class")
	fallback_model: str | None = Field(default=None, max_length=200, description="What a caller would send in x-openproxy-fallback-model")


class DataClassOut(BaseModel):
	model_config = ConfigDict(populate_by_name=True)

	class_: str = Field(alias="class")
	source: str
	entities: list[str]


class PolicyOut(BaseModel):
	mode: str
	allowed: bool
	action: str
	reason_code: str | None
	detail: str | None
	triggered_rules: list[str]


class RoutingOut(BaseModel):
	current_mode: str = Field(description="The org's routing_mode now. The decision below is always what enforce would do.")
	requested: str
	model: str | None = Field(description="The model that would serve the request, or null if none is authorized")
	reason: str
	authorized: list[str]
	excluded: dict[str, str]
	key_alias: str | None = Field(description="Which provider key would serve it (never the key itself)")


class FallbackOut(BaseModel):
	model: str
	authorized: bool
	reason: str


class PolicyPreviewResponse(BaseModel):
	verdict: Literal["allowed", "blocked_by_policy", "blocked_by_routing", "would_block_if_enforced"]
	data_class: DataClassOut
	policy: PolicyOut
	routing: RoutingOut
	fallback: FallbackOut | None
	not_evaluated: list[str]
