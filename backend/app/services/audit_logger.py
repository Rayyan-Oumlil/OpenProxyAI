"""Async background task for logging LLM requests to PostgreSQL and Redis."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from redis.asyncio import Redis

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.request_log import RequestLog
from app.services.cost_tracker import cost_tracker_service


async def log_request(
	redis: Redis,
	request_id: uuid.UUID,
	org_id: uuid.UUID,
	user_id: uuid.UUID,
	api_key_id: uuid.UUID | None,
	model: str,
	provider: str,
	prompt_tokens: int,
	completion_tokens: int,
	cost_usd: Decimal,
	latency_ms: int,
	ttft_ms: int | None,
	status_code: int,
	error_message: str | None = None,
	request_metadata: dict | None = None,
) -> None:
	total_tokens = prompt_tokens + completion_tokens
	async with AsyncSessionLocal() as db:
		row = RequestLog(
			request_id=request_id,
			org_id=org_id,
			user_id=user_id,
			api_key_id=api_key_id,
			model=model,
			provider=provider,
			prompt_tokens=prompt_tokens,
			completion_tokens=completion_tokens,
			total_tokens=total_tokens,
			cost_usd=cost_usd,
			latency_ms=latency_ms,
			ttft_ms=ttft_ms,
			status_code=status_code,
			error_message=error_message,
			request_metadata=request_metadata or {},
		)
		db.add(row)
		await db.commit()

	today = datetime.now(UTC).strftime("%Y-%m-%d")
	org_spend_key = f"rl:usd:{org_id}:{today}"
	user_spend_key = f"rl:usd:user:{user_id}:{today}"
	org_spend = await redis.incrbyfloat(org_spend_key, float(cost_usd))
	await redis.expire(org_spend_key, 48 * 3600)
	await redis.incrbyfloat(user_spend_key, float(cost_usd))
	await redis.expire(user_spend_key, 48 * 3600)

	await cost_tracker_service.alert_at_threshold(
		redis=redis,
		org_id=org_id,
		current_spend=Decimal(str(org_spend or "0")),
		budget_daily_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)),
	)

