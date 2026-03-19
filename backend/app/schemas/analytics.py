"""Analytics response schemas — overview, cost breakdowns, usage trends."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class UsageOverview(BaseModel):
	period_days: int
	total_requests: int
	successful_requests: int
	failed_requests: int
	policy_blocked_requests: int = 0
	policy_flagged_requests: int = 0
	total_tokens: int
	total_cost_usd: float
	avg_latency_ms: float
	avg_ttft_ms: float
	p50_latency_ms: int | None = None
	p95_latency_ms: int | None = None
	p99_latency_ms: int | None = None
	projected_month_end_cost_usd: float | None = None
	forecast_basis_days: int | None = None


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


class PolicyActionStat(BaseModel):
	action: str
	count: int


class PolicyReasonStat(BaseModel):
	reason_code: str
	action: str
	count: int


class PolicyAnalyticsResponse(BaseModel):
	period_days: int
	total_policy_events: int
	by_action: list[PolicyActionStat]
	by_reason: list[PolicyReasonStat]
	generated_at: datetime


class CacheAnalyticsResponse(BaseModel):
	period_days: int
	exact_hits: int
	semantic_hits: int
	misses: int
	hit_rate: float
	estimated_savings_usd: float
