"""Redis rate limiter with fixed-window RPM, TPM, and daily org/user budget checks."""

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
		retry_after: int | None = None,
	) -> dict[str, str]:
		out = {
			"X-RateLimit-Requests-Limit": str(max_rpm),
			"X-RateLimit-Requests-Remaining": str(max(requests_remaining, 0)),
			"X-RateLimit-Tokens-Limit": str(max_tpm),
			"X-RateLimit-Tokens-Remaining": str(max(tokens_remaining, 0)),
			"X-RateLimit-Budget-Daily-USD": f"{max_daily_budget_usd:.2f}",
			"X-RateLimit-Budget-Remaining-USD": f"{max(budget_remaining, Decimal('0')):.6f}",
			"X-RateLimit-Reset": str(reset_epoch),
		}
		if retry_after is not None:
			out = {**out, "Retry-After": str(retry_after)}
		return out

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
		team_id: str | None = None,
		team_budget_monthly_usd: Decimal | None = None,
		model: str | None = None,
		policy_config: object | None = None,
	) -> tuple[bool, dict[str, str], str | None, str | None, int | None]:
		now = datetime.now(UTC)
		now_ms = int(time.time() * 1000)
		window_start_ms = now_ms - 60_000
		minute_bucket = int(now.timestamp()) // 60
		day_key = now.strftime("%Y-%m-%d")
		rpm_key = f"rl:req:{org_id}:{minute_bucket}"
		tpm_key = f"rl:tok:{org_id}:{minute_bucket}"
		org_usd_key = f"rl:usd:{org_id}:{day_key}"
		user_usd_key = f"rl:usd:user:{user_id}:{day_key}"

		# Team-level limits from policy (when request has team_id)
		per_team = (
			getattr(policy_config, "per_team_limits", None) or {} if policy_config else {}
		)
		team_rpm_limit = per_team.get("rpm") if isinstance(per_team.get("rpm"), int) else None
		team_tpm_limit = per_team.get("tpm") if isinstance(per_team.get("tpm"), int) else None
		team_limits_active = (
			team_id is not None
			and (team_rpm_limit is not None or team_tpm_limit is not None)
		)
		team_rpm_key = f"rl:req:team:{team_id}:{minute_bucket}" if team_id else None
		team_tpm_key = f"rl:tok:team:{team_id}:{minute_bucket}" if team_id else None

		# Fixed-window RPM counter: INCR then EXPIRE on first request in window.
		# Read TPM and budget counters in the same pipeline.
		pipe = redis.pipeline(transaction=True)
		pipe.incr(rpm_key)
		pipe.expire(rpm_key, 120)
		pipe.get(tpm_key)
		pipe.get(org_usd_key)
		pipe.get(user_usd_key)
		if team_limits_active:
			pipe.get(team_rpm_key)
			pipe.get(team_tpm_key)
		pipe_results = await pipe.execute()
		current_req_count = pipe_results[0]
		current_tpm_raw = pipe_results[2]
		org_spend_raw = pipe_results[3]
		user_spend_raw = pipe_results[4]
		if team_limits_active:
			team_req_raw = pipe_results[5]
			team_tpm_raw = pipe_results[6]
		else:
			team_req_raw = None
			team_tpm_raw = None

		# Set TTL only on the first request in this window.
		if current_req_count == 1:
			await redis.expire(rpm_key, 120)

		current_tpm = int(current_tpm_raw or 0)
		org_spend = Decimal(str(org_spend_raw or "0"))
		user_spend = Decimal(str(user_spend_raw or "0"))
		est_tokens = max(request_tokens_estimate, 1)

		minute_reset_epoch = self._minute_reset_epoch(now)
		org_budget_remaining = max_daily_budget_usd - org_spend

		if current_req_count > max_rpm:
			retry_after = self._seconds_until(minute_reset_epoch)
			headers = self._headers(
				max_rpm=max_rpm,
				max_tpm=max_tpm,
				max_daily_budget_usd=max_daily_budget_usd,
				requests_remaining=0,
				tokens_remaining=max_tpm - current_tpm,
				budget_remaining=org_budget_remaining,
				reset_epoch=minute_reset_epoch,
				retry_after=retry_after,
			)
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
				retry_after=retry_after,
			)
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
				retry_after=retry_after,
			)
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
				retry_after=retry_after,
			)
			return (
				False,
				headers,
				"user_budget_daily_usd",
				f"Daily user budget reached. Resets in {retry_after} seconds.",
				retry_after,
			)

		# Team RPM/TPM — when per_team_limits set and request has team_id
		if team_limits_active:
			team_req_count = int(team_req_raw or 0)
			team_tpm = int(team_tpm_raw or 0)
			if team_rpm_limit is not None and team_req_count >= team_rpm_limit:
				retry_after = self._seconds_until(minute_reset_epoch)
				headers = self._headers(
					max_rpm=max_rpm,
					max_tpm=max_tpm,
					max_daily_budget_usd=max_daily_budget_usd,
					requests_remaining=max_rpm - current_req_count,
					tokens_remaining=max_tpm - current_tpm,
					budget_remaining=org_budget_remaining,
					reset_epoch=minute_reset_epoch,
					retry_after=retry_after,
				)
				return (
					False,
					headers,
					"team_requests_per_minute",
					f"Team limit: {team_rpm_limit} requests/minute. Resets in {retry_after} seconds.",
					retry_after,
				)
			if team_tpm_limit is not None and team_tpm + est_tokens > team_tpm_limit:
				retry_after = self._seconds_until(minute_reset_epoch)
				headers = self._headers(
					max_rpm=max_rpm,
					max_tpm=max_tpm,
					max_daily_budget_usd=max_daily_budget_usd,
					requests_remaining=max_rpm - current_req_count,
					tokens_remaining=max_tpm - current_tpm,
					budget_remaining=org_budget_remaining,
					reset_epoch=minute_reset_epoch,
					retry_after=retry_after,
				)
				return (
					False,
					headers,
					"team_tokens_per_minute",
					f"Team limit: {team_tpm_limit} tokens/minute. Resets in {retry_after} seconds.",
					retry_after,
				)

		# Team monthly budget — independent of org budget (both must pass)
		if team_id is not None and team_budget_monthly_usd is not None:
			month_key = now.strftime("%Y-%m")
			team_usd_key = f"rl:usd:team:{team_id}:{month_key}"
			team_spend_raw = await redis.get(team_usd_key)
			team_spend = Decimal(str(team_spend_raw or "0"))
			if team_spend >= team_budget_monthly_usd:
				from calendar import monthrange
				_, last_day = monthrange(now.year, now.month)
				next_month_start = (now.replace(day=last_day) + timedelta(days=1)).replace(
					hour=0, minute=0, second=0, microsecond=0
				)
				budget_reset_epoch = int(next_month_start.timestamp())
				retry_after = self._seconds_until(budget_reset_epoch)
				headers = self._headers(
					max_rpm=max_rpm,
					max_tpm=max_tpm,
					max_daily_budget_usd=max_daily_budget_usd,
					requests_remaining=max_rpm - current_req_count,
					tokens_remaining=max_tpm - current_tpm,
					budget_remaining=org_budget_remaining,
					reset_epoch=minute_reset_epoch,
					retry_after=retry_after,
				)
				return (
					False,
					headers,
					"team_budget_monthly_usd",
					"Team monthly budget reached. Resets at start of next month.",
					retry_after,
				)

		# Per-model rate limits
		if model and policy_config is not None:
			model_rate_limits = getattr(policy_config, "model_rate_limits", {}) or {}
			model_limits = model_rate_limits.get(model, {})
			if model_limits:
				model_rpm = model_limits.get("rpm")
				model_tpm = model_limits.get("tpm")

				if model_rpm is not None:
					model_req_key = f"rl:req:{org_id}:{model}"
					model_pipe = redis.pipeline(transaction=True)
					model_pipe.zremrangebyscore(model_req_key, 0, window_start_ms)
					model_pipe.zcard(model_req_key)
					model_pipe.zrange(model_req_key, 0, 0, withscores=True)
					_, model_req_count, model_oldest_entry = await model_pipe.execute()
					if model_req_count >= model_rpm:
						if model_oldest_entry:
							model_oldest_score = int(model_oldest_entry[0][1])
							retry_after = max(((model_oldest_score + 60_000) - now_ms + 999) // 1000, 1)
						else:
							retry_after = self._seconds_until(minute_reset_epoch)
						headers = self._headers(
							max_rpm=max_rpm,
							max_tpm=max_tpm,
							max_daily_budget_usd=max_daily_budget_usd,
							requests_remaining=max_rpm - current_req_count,
							tokens_remaining=max_tpm - current_tpm,
							budget_remaining=org_budget_remaining,
							reset_epoch=minute_reset_epoch,
							retry_after=retry_after,
						)
						return (
							False,
							headers,
							f"model_rpm:{model}",
							f"{model_rpm} requests/minute limit for {model} reached. Resets in {retry_after} seconds.",
							retry_after,
						)

				if model_tpm is not None:
					model_tok_key = f"rl:tok:{org_id}:{model}:{minute_bucket}"
					model_tok_raw = await redis.get(model_tok_key)
					model_current_tpm = int(model_tok_raw or 0)
					if model_current_tpm + est_tokens > model_tpm:
						retry_after = self._seconds_until(minute_reset_epoch)
						headers = self._headers(
							max_rpm=max_rpm,
							max_tpm=max_tpm,
							max_daily_budget_usd=max_daily_budget_usd,
							requests_remaining=max_rpm - current_req_count,
							tokens_remaining=max_tpm - current_tpm,
							budget_remaining=org_budget_remaining,
							reset_epoch=minute_reset_epoch,
							retry_after=retry_after,
						)
						return (
							False,
							headers,
							f"model_tpm:{model}",
							f"{model_tpm} tokens/minute limit for {model} reached. Resets in {retry_after} seconds.",
							retry_after,
						)

		# Atomic consume for token counter (request already counted by INCR above).
		consume = redis.pipeline(transaction=True)
		consume.incrby(tpm_key, est_tokens)
		consume.expire(tpm_key, 120)
		if team_limits_active:
			consume.incr(team_rpm_key)
			consume.expire(team_rpm_key, 120)
			consume.incrby(team_tpm_key, est_tokens)
			consume.expire(team_tpm_key, 120)
		if model and policy_config is not None:
			model_rate_limits = getattr(policy_config, "model_rate_limits", {}) or {}
			if model_rate_limits.get(model):
				model_req_key = f"rl:req:{org_id}:{model}"
				model_tok_key = f"rl:tok:{org_id}:{model}:{minute_bucket}"
				request_member = f"{now_ms}:{uuid.uuid4().hex}"
				consume.zadd(model_req_key, {request_member: now_ms})
				consume.expire(model_req_key, 120)
				consume.incrby(model_tok_key, est_tokens)
				consume.expire(model_tok_key, 120)
		results = await consume.execute()
		tok_count_after = results[0]

		headers = self._headers(
			max_rpm=max_rpm,
			max_tpm=max_tpm,
			max_daily_budget_usd=max_daily_budget_usd,
			requests_remaining=max_rpm - current_req_count,
			tokens_remaining=max_tpm - int(tok_count_after),
			budget_remaining=org_budget_remaining,
			reset_epoch=minute_reset_epoch,
		)
		return True, headers, None, None, None


rate_limiter_service = RateLimiterService()
