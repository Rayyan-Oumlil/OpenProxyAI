"""Analytics response schemas — overview, cost breakdowns, usage trends."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class UsageOverview(BaseModel):
	period_days: int
	total_requests: int
	successful_requests: int
	failed_requests: int
	total_tokens: int
	total_cost_usd: float
	avg_latency_ms: float
	avg_ttft_ms: float


class CostByModel(BaseModel):
	model: str
	provider: str
	requests: int
	tokens: int
	cost_usd: float


class CostByUser(BaseModel):
	user_id: uuid.UUID
	email: str
	requests: int
	tokens: int
	cost_usd: float


class DailyUsageTrend(BaseModel):
	date: str
	requests: int
	tokens: int
	cost_usd: float
	avg_latency_ms: float


class AnalyticsResponse(BaseModel):
	overview: UsageOverview
	by_model: list[CostByModel]
	by_user: list[CostByUser]
	daily_trend: list[DailyUsageTrend]
	generated_at: datetime
