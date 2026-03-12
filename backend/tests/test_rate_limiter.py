"""Rate limiter unit tests for RPM/TPM and org/user budget enforcement."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.rate_limiter import rate_limiter_service


@pytest.mark.asyncio
async def test_check_limits_success_returns_full_headers(fake_redis):
	ok, headers, limit_type, detail, retry_after = await rate_limiter_service.check_limits(
		redis=fake_redis,
		org_id="org-1",
		user_id="user-1",
		request_tokens_estimate=100,
		max_rpm=60,
		max_tpm=100000,
		max_daily_budget_usd=Decimal("50"),
	)

	assert ok is True
	assert limit_type is None
	assert detail is None
	assert retry_after is None
	assert "X-RateLimit-Requests-Limit" in headers
	assert "X-RateLimit-Requests-Remaining" in headers
	assert "X-RateLimit-Tokens-Limit" in headers
	assert "X-RateLimit-Tokens-Remaining" in headers
	assert "X-RateLimit-Budget-Daily-USD" in headers
	assert "X-RateLimit-Budget-Remaining-USD" in headers
	assert "X-RateLimit-Reset" in headers


@pytest.mark.asyncio
async def test_check_limits_requests_per_minute_exceeded(fake_redis):
	first = await rate_limiter_service.check_limits(
		redis=fake_redis,
		org_id="org-2",
		user_id="user-2",
		request_tokens_estimate=10,
		max_rpm=1,
		max_tpm=1000,
		max_daily_budget_usd=Decimal("50"),
	)
	assert first[0] is True

	ok, headers, limit_type, detail, retry_after = await rate_limiter_service.check_limits(
		redis=fake_redis,
		org_id="org-2",
		user_id="user-2",
		request_tokens_estimate=10,
		max_rpm=1,
		max_tpm=1000,
		max_daily_budget_usd=Decimal("50"),
	)

	assert ok is False
	assert limit_type == "requests_per_minute"
	assert detail is not None
	assert retry_after is not None and retry_after > 0
	assert headers["X-RateLimit-Requests-Remaining"] == "0"
	assert headers["Retry-After"] == str(retry_after)


@pytest.mark.asyncio
async def test_check_limits_tokens_per_minute_exceeded(fake_redis):
	# First request consumes most of the TPM budget.
	first = await rate_limiter_service.check_limits(
		redis=fake_redis,
		org_id="org-tpm",
		user_id="user-tpm",
		request_tokens_estimate=90,
		max_rpm=60,
		max_tpm=100,
		max_daily_budget_usd=Decimal("50"),
	)
	assert first[0] is True

	# Second request should exceed tokens per minute.
	ok, headers, limit_type, detail, retry_after = await rate_limiter_service.check_limits(
		redis=fake_redis,
		org_id="org-tpm",
		user_id="user-tpm",
		request_tokens_estimate=20,
		max_rpm=60,
		max_tpm=100,
		max_daily_budget_usd=Decimal("50"),
	)

	assert ok is False
	assert limit_type == "tokens_per_minute"
	assert detail is not None
	assert retry_after is not None and retry_after > 0
	assert headers["X-RateLimit-Tokens-Remaining"] == "0"
	assert headers["Retry-After"] == str(retry_after)


@pytest.mark.asyncio
async def test_check_limits_org_budget_exceeded(fake_redis):
	today = datetime.now(UTC).strftime("%Y-%m-%d")
	await fake_redis.incrbyfloat(f"rl:usd:org-3:{today}", 50.0)

	ok, headers, limit_type, detail, retry_after = await rate_limiter_service.check_limits(
		redis=fake_redis,
		org_id="org-3",
		user_id="user-3",
		request_tokens_estimate=10,
		max_rpm=60,
		max_tpm=100000,
		max_daily_budget_usd=Decimal("50"),
	)

	assert ok is False
	assert limit_type == "budget_daily_usd"
	assert detail is not None
	assert retry_after is not None and retry_after > 0
	assert headers["X-RateLimit-Budget-Remaining-USD"] == "0.000000"


@pytest.mark.asyncio
async def test_check_limits_user_budget_exceeded(fake_redis):
	today = datetime.now(UTC).strftime("%Y-%m-%d")
	await fake_redis.incrbyfloat(f"rl:usd:user:user-4:{today}", 10.0)

	ok, headers, limit_type, detail, retry_after = await rate_limiter_service.check_limits(
		redis=fake_redis,
		org_id="org-4",
		user_id="user-4",
		request_tokens_estimate=10,
		max_rpm=60,
		max_tpm=100000,
		max_daily_budget_usd=Decimal("50"),
		user_daily_budget_usd=Decimal("10"),
	)

	assert ok is False
	assert limit_type == "user_budget_daily_usd"
	assert detail is not None
	assert retry_after is not None and retry_after > 0
	assert "Retry-After" in headers
