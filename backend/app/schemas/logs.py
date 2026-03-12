"""Logs schemas — paginated request logs for analytics endpoint."""

import uuid
from datetime import datetime
from typing import Generic, TypeVar

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


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
	items: list[T]
	total: int
	page: int
	page_size: int
	total_pages: int
