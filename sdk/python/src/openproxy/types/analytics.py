from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CostByModel:
    model: str
    provider: str
    requests: int
    tokens: int
    cost_usd: float

@dataclass
class DailyTrend:
    date: str
    requests: int
    tokens: int
    cost_usd: float
    avg_latency_ms: float

@dataclass
class UsageOverview:
    period_days: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    avg_ttft_ms: float
    policy_blocked_requests: int = 0
    policy_flagged_requests: int = 0

@dataclass
class AnalyticsResponse:
    overview: UsageOverview
    by_model: list[CostByModel]
    daily_trend: list[DailyTrend]
    generated_at: str
