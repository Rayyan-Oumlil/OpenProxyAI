"""Policy configuration schemas — request/response for the policy config API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PolicyConfigRequest(BaseModel):
	"""Partial update — only provided fields are changed."""

	enforcement_mode: Literal["off", "log_only", "enforce"] | None = None
	allowed_models: list[str] | None = None
	blocked_keywords: list[str] | None = None
	pii_detection_enabled: bool | None = None
	pii_entities: list[str] | None = None


class PolicyConfigResponse(BaseModel):
	enforcement_mode: str
	allowed_models: list[str]
	blocked_keywords: list[str]
	pii_detection_enabled: bool
	pii_entities: list[str]
	updated_at: datetime | None
