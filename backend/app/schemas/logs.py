"""Logs schemas — paginated request logs for analytics endpoint."""

import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class RequestLogItem(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	created_at: datetime
	model: str
	provider: str
	status: str
	prompt_tokens: int
	completion_tokens: int
	total_tokens: int
	cost_usd: float
	latency_ms: int | None
	ttft_ms: int | None
	error_message: str | None
	policy_action: str | None = None
	policy_reason: str | None = None
	policy_triggered_rules: list[str] | None = None


class RequestLogDetail(RequestLogItem):
	"""Full detail for a single log entry — includes fields omitted from the list view."""

	request_id: uuid.UUID
	user_id: uuid.UUID
	api_key_id: uuid.UUID | None
	status_code: int
	request_metadata: dict[str, Any]


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
	items: list[T]
	total: int
	page: int
	page_size: int
	total_pages: int
