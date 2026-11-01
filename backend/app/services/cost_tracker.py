"""Budget enforcement — spend tracking, threshold alerts, daily caps."""

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from litellm import completion_cost
from redis.asyncio import Redis


def _today_iso() -> str:
	return datetime.now(UTC).strftime("%Y-%m-%d")


class CostTrackerService:
	@staticmethod
	def calculate_cost_usd(completion_response: object) -> Decimal:
		cost = completion_cost(completion_response=completion_response)
		return Decimal(str(cost)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

	async def get_org_spend_today(self, redis: Redis, org_id: UUID | str) -> Decimal:
		key = f"rl:usd:{org_id}:{_today_iso()}"
		raw = await redis.get(key)
		return Decimal(str(raw or "0"))

	async def get_user_spend_today(self, redis: Redis, user_id: UUID | str) -> Decimal:
		key = f"rl:usd:user:{user_id}:{_today_iso()}"
		raw = await redis.get(key)
		return Decimal(str(raw or "0"))

	async def check_user_budget(
		self,
		redis: Redis,
		user_id: UUID | str,
		user_budget_daily_usd: Decimal | None,
	) -> bool:
		if user_budget_daily_usd is None:
			return True
		spend = await self.get_user_spend_today(redis, user_id)
		return spend < user_budget_daily_usd

	async def alert_at_threshold(
		self,
		redis: Redis,
		org_id: UUID | str,
		current_spend: Decimal,
		budget_daily_usd: Decimal,
		threshold: float = 0.8,
	) -> bool:
		if budget_daily_usd <= Decimal("0"):
			return False
		trigger = budget_daily_usd * Decimal(str(threshold))
		if current_spend < trigger:
			return False
		alert_key = f"alert:budget:{org_id}:{_today_iso()}"
		was_set = await redis.set(alert_key, "1", ex=86400, nx=True)
		if not was_set:
			return False

		# Webhook — budget alert
		import asyncio
		asyncio.create_task(_fire_budget_webhook(
			org_id=str(org_id),
			spend=float(current_spend),
			budget=float(budget_daily_usd),
		))

		return True


	async def check_anomaly(
		self,
		redis,
		org_id: str,
		user_id,
		db_session,
		org,
	) -> None:
		"""
		Check if today's org spend is anomalously high vs. 7-day baseline.
		Fires cost.anomaly webhook if threshold exceeded (at most once per hour).
		Fire-and-forget — exceptions are swallowed.
		"""
		try:
			from datetime import datetime, timezone
			from app.config import settings

			today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

			# Get today's spend from existing Redis key
			today_key = f"rl:usd:{org_id}:{today_str}"
			today_raw = await redis.get(today_key)
			today_spend = float(today_raw or 0)

			# Update baseline: one entry per day, spend stored as score
			baseline_key = f"cost:baseline:{org_id}"
			await redis.zadd(baseline_key, {today_str: today_spend})
			await redis.expire(baseline_key, 86400 * 10)  # keep 10 days

			# Get all baseline entries (member=date, score=spend)
			entries = await redis.zrange(baseline_key, 0, -1, withscores=True)

			if len(entries) >= settings.COST_ANOMALY_MIN_BASELINE_DAYS:
				values = [score for _member, score in entries]

				if values:
					avg = sum(values) / len(values)
					if avg > 0 and today_spend > avg * settings.COST_ANOMALY_MULTIPLIER:
						now_hour = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
						fired_key = f"cost:anomaly_fired:{org_id}:{now_hour}"
						already_fired = await redis.get(fired_key)
						if not already_fired:
							await redis.setex(fired_key, 3600, "1")
							from app.services import webhook_service as _webhook_svc
							await _webhook_svc.dispatch_event(
								db=db_session,
								org=org,
								event_type="cost.anomaly",
								data={
									"today_spend_usd": round(today_spend, 6),
									"baseline_avg_usd": round(avg, 6),
									"multiplier": round(today_spend / avg, 2),
									"org_id": str(org_id),
								},
							)

			# Per-user anomaly check
			if user_id is not None:
				user_today_key = f"rl:usd:user:{user_id}:{today_str}"
				user_raw = await redis.get(user_today_key)
				user_today_spend = float(user_raw or 0)

				user_baseline_key = f"cost:baseline:user:{user_id}"
				await redis.zadd(user_baseline_key, {today_str: user_today_spend})
				await redis.expire(user_baseline_key, 86400 * 10)

				user_entries = await redis.zrange(user_baseline_key, 0, -1, withscores=True)

				if len(user_entries) >= settings.COST_ANOMALY_MIN_BASELINE_DAYS:
					user_values = [score for _member, score in user_entries]

					if user_values:
						user_avg = sum(user_values) / len(user_values)
						if user_avg > 0 and user_today_spend > user_avg * settings.COST_ANOMALY_MULTIPLIER:
							now_hour = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
							user_fired_key = f"cost:anomaly_fired:user:{user_id}:{now_hour}"
							user_already_fired = await redis.get(user_fired_key)
							if not user_already_fired:
								await redis.setex(user_fired_key, 3600, "1")
								from app.services import webhook_service as _webhook_svc
								await _webhook_svc.dispatch_event(
									db=db_session,
									org=org,
									event_type="cost.anomaly",
									data={
										"today_spend_usd": round(user_today_spend, 6),
										"baseline_avg_usd": round(user_avg, 6),
										"multiplier": round(user_today_spend / user_avg, 2),
										"org_id": str(org_id),
									},
								)
		except Exception as exc:
			import logging
			logging.getLogger(__name__).warning("Cost anomaly check failed: %s", exc)


async def _fire_budget_webhook(org_id: str, spend: float, budget: float) -> None:
	"""Fire-and-forget webhook for budget threshold alert. Swallows all exceptions."""
	try:
		from uuid import UUID as _UUID

		from app.database import org_scoped_session
		from app.models.organization import Organization as _Org
		from app.services import webhook_service

		async with org_scoped_session(_UUID(org_id)) as _db:
			_org = await _db.get(_Org, _UUID(org_id))
			if _org is not None:
				await webhook_service.dispatch_event(
					db=_db,
					org=_org,
					event_type="budget.alert",
					data={
						"spend_usd": round(spend, 4),
						"budget_usd": round(budget, 4),
						"percent_used": round(spend / budget * 100, 1) if budget else 0,
					},
				)
	except Exception as exc:
		import logging as _logging
		_logging.getLogger(__name__).error(
			"budget.alert webhook failed for org %s (spend=%.4f budget=%.4f): %s",
			org_id, spend, budget, exc,
		)


cost_tracker_service = CostTrackerService()

