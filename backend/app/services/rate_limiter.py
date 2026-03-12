"""Redis rate limiter with sliding RPM, TPM, and daily org/user budget checks."""

import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis


class RateLimiterService:
	@staticmethod
	def _minute_reset_epoch(now: datetime) -> int:
		reset_at = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
		return int(reset_at.timestamp())

	@staticmethod
	def _seconds_until(ts: int) -> int:
		return max(ts - int(time.time()), 1)

	@staticmethod
	def _next_day_reset_epoch(now: datetime) -> int:
		tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
		return int(tomorrow.timestamp())

	@staticmethod
	def _headers(
		max_rpm: int,
		max_tpm: int,
		max_daily_budget_usd: Decimal,
		requests_remaining: int,
		tokens_remaining: int,
		budget_remaining: Decimal,
		reset_epoch: int,
	) -> dict[str, str]:
		return {
			"X-RateLimit-Requests-Limit": str(max_rpm),
			"X-RateLimit-Requests-Remaining": str(max(requests_remaining, 0)),
			"X-RateLimit-Tokens-Limit": str(max_tpm),
			"X-RateLimit-Tokens-Remaining": str(max(tokens_remaining, 0)),
			"X-RateLimit-Budget-Daily-USD": f"{max_daily_budget_usd:.2f}",
			"X-RateLimit-Budget-Remaining-USD": f"{max(budget_remaining, Decimal('0')):.6f}",
			"X-RateLimit-Reset": str(reset_epoch),
		}

	async def check_limits(
		self,
		redis: Redis,
		org_id: str,
		user_id: str,
		request_tokens_estimate: int,
		max_rpm: int,
		max_tpm: int,
		max_daily_budget_usd: Decimal,
		user_daily_budget_usd: Decimal | None = None,
	) -> tuple[bool, dict[str, str], str | None, str | None, int | None]:
		now = datetime.now(UTC)
		now_ms = int(time.time() * 1000)
		window_start_ms = now_ms - 60_000
		minute_bucket = int(now.timestamp()) // 60
		day_key = now.strftime("%Y-%m-%d")
		rpm_key = f"rl:req:{org_id}"
		tpm_key = f"rl:tok:{org_id}:{minute_bucket}"
		org_usd_key = f"rl:usd:{org_id}:{day_key}"
		user_usd_key = f"rl:usd:user:{user_id}:{day_key}"

		# Read current counters after pruning sliding-window request entries.
		pipe = redis.pipeline(transaction=True)
		pipe.zremrangebyscore(rpm_key, 0, window_start_ms)
		pipe.zcard(rpm_key)
		pipe.zrange(rpm_key, 0, 0, withscores=True)
		pipe.get(tpm_key)
		pipe.get(org_usd_key)
		pipe.get(user_usd_key)
		_, current_req_count, oldest_entry, current_tpm_raw, org_spend_raw, user_spend_raw = await pipe.execute()

		current_tpm = int(current_tpm_raw or 0)
		org_spend = Decimal(str(org_spend_raw or "0"))
		user_spend = Decimal(str(user_spend_raw or "0"))
		est_tokens = max(request_tokens_estimate, 1)

		minute_reset_epoch = self._minute_reset_epoch(now)
		org_budget_remaining = max_daily_budget_usd - org_spend

		if current_req_count >= max_rpm:
			if oldest_entry:
				oldest_score = int(oldest_entry[0][1])
				retry_after = max(((oldest_score + 60_000) - now_ms + 999) // 1000, 1)
			else:
				retry_after = self._seconds_until(minute_reset_epoch)
			headers = self._headers(
				max_rpm=max_rpm,
				max_tpm=max_tpm,
				max_daily_budget_usd=max_daily_budget_usd,
				requests_remaining=0,
				tokens_remaining=max_tpm - current_tpm,
				budget_remaining=org_budget_remaining,
				reset_epoch=minute_reset_epoch,
			)
			headers["Retry-After"] = str(retry_after)
			return (
				False,
				headers,
				"requests_per_minute",
				f"{max_rpm} requests/minute limit reached. Resets in {retry_after} seconds.",
				retry_after,
			)

		if current_tpm + est_tokens > max_tpm:
			retry_after = self._seconds_until(minute_reset_epoch)
			headers = self._headers(
				max_rpm=max_rpm,
				max_tpm=max_tpm,
				max_daily_budget_usd=max_daily_budget_usd,
				requests_remaining=max_rpm - current_req_count,
				tokens_remaining=0,
				budget_remaining=org_budget_remaining,
				reset_epoch=minute_reset_epoch,
			)
			headers["Retry-After"] = str(retry_after)
			return (
				False,
				headers,
				"tokens_per_minute",
				f"{max_tpm} tokens/minute limit reached. Resets in {retry_after} seconds.",
				retry_after,
			)

		if org_budget_remaining <= Decimal("0"):
			budget_reset_epoch = self._next_day_reset_epoch(now)
			retry_after = self._seconds_until(budget_reset_epoch)
			headers = self._headers(
				max_rpm=max_rpm,
				max_tpm=max_tpm,
				max_daily_budget_usd=max_daily_budget_usd,
				requests_remaining=max_rpm - current_req_count,
				tokens_remaining=max_tpm - current_tpm,
				budget_remaining=Decimal("0"),
				reset_epoch=budget_reset_epoch,
			)
			headers["Retry-After"] = str(retry_after)
			return (
				False,
				headers,
				"budget_daily_usd",
				f"Daily org budget reached. Resets in {retry_after} seconds.",
				retry_after,
			)

		if user_daily_budget_usd is not None and user_spend >= user_daily_budget_usd:
			budget_reset_epoch = self._next_day_reset_epoch(now)
			retry_after = self._seconds_until(budget_reset_epoch)
			headers = self._headers(
				max_rpm=max_rpm,
				max_tpm=max_tpm,
				max_daily_budget_usd=max_daily_budget_usd,
				requests_remaining=max_rpm - current_req_count,
				tokens_remaining=max_tpm - current_tpm,
				budget_remaining=org_budget_remaining,
				reset_epoch=budget_reset_epoch,
			)
			headers["Retry-After"] = str(retry_after)
			return (
				False,
				headers,
				"user_budget_daily_usd",
				f"Daily user budget reached. Resets in {retry_after} seconds.",
				retry_after,
			)

		# Atomic consume for request and token counters.
		request_member = f"{now_ms}:{uuid.uuid4().hex}"
		consume = redis.pipeline(transaction=True)
		consume.zadd(rpm_key, {request_member: now_ms})
		consume.expire(rpm_key, 120)
		consume.incrby(tpm_key, est_tokens)
		consume.expire(tpm_key, 120)
		_, _, tok_count_after, _ = await consume.execute()
		req_count_after = current_req_count + 1

		headers = self._headers(
			max_rpm=max_rpm,
			max_tpm=max_tpm,
			max_daily_budget_usd=max_daily_budget_usd,
			requests_remaining=max_rpm - req_count_after,
			tokens_remaining=max_tpm - int(tok_count_after),
			budget_remaining=org_budget_remaining,
			reset_epoch=minute_reset_epoch,
		)
		return True, headers, None, None, None


rate_limiter_service = RateLimiterService()

