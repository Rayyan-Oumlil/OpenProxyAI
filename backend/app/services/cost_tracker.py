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
		if await redis.exists(alert_key):
			return False
		await redis.setex(alert_key, 86400, "1")
		return True


cost_tracker_service = CostTrackerService()

