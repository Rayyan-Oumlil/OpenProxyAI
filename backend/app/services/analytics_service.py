"""Analytics service querying mv_daily_spend and request logs with org isolation."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import ceil
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics import (
	AnalyticsResponse,
	CostByModel,
	CostByUser,
	DailyUsageTrend,
	UsageOverview,
)
from app.schemas.logs import Page, RequestLogItem


class AnalyticsService:
	async def get_overview(
		self,
		db: AsyncSession,
		org_id: UUID,
		period_days: int = 30,
	) -> AnalyticsResponse:
		since = datetime.now(UTC).date() - timedelta(days=period_days - 1)
		overview = await self._overview_stats(db, org_id, since, period_days)
		by_model = await self._cost_by_model(db, org_id, since)
		by_user = await self._cost_by_user(db, org_id, since)
		daily_trend = await self._daily_trend(db, org_id, since)
		return AnalyticsResponse(
			overview=overview,
			by_model=by_model,
			by_user=by_user,
			daily_trend=daily_trend,
			generated_at=datetime.now(UTC),
		)

	async def _overview_stats(
		self,
		db: AsyncSession,
		org_id: UUID,
		since: date,
		period_days: int,
	) -> UsageOverview:
		mv_row = (
			await db.execute(
				text(
					"""
					SELECT
						COALESCE(SUM(total_requests), 0) AS total_requests,
						COALESCE(SUM(total_prompt_tokens + total_completion_tokens), 0) AS total_tokens,
						COALESCE(SUM(total_cost_usd), 0) AS total_cost_usd,
						COALESCE(AVG(avg_latency_ms), 0) AS avg_latency_ms
					FROM mv_daily_spend
					WHERE org_id = :org_id
					  AND day::date >= :since
					"""
				),
				{"org_id": str(org_id), "since": since},
			)
		).mappings().one()

		log_row = (
			await db.execute(
				text(
					"""
					SELECT
						COALESCE(SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END), 0) AS successful_requests,
						COALESCE(SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END), 0) AS failed_requests,
						COALESCE(AVG(ttft_ms), 0) AS avg_ttft_ms
					FROM request_logs
					WHERE org_id = :org_id
					  AND created_at::date >= :since
					"""
				),
				{"org_id": str(org_id), "since": since},
			)
		).mappings().one()

		return UsageOverview(
			period_days=period_days,
			total_requests=int(mv_row["total_requests"] or 0),
			successful_requests=int(log_row["successful_requests"] or 0),
			failed_requests=int(log_row["failed_requests"] or 0),
			total_tokens=int(mv_row["total_tokens"] or 0),
			total_cost_usd=float(Decimal(str(mv_row["total_cost_usd"] or 0))),
			avg_latency_ms=float(mv_row["avg_latency_ms"] or 0),
			avg_ttft_ms=float(log_row["avg_ttft_ms"] or 0),
		)

	async def _cost_by_model(
		self,
		db: AsyncSession,
		org_id: UUID,
		since: date,
	) -> list[CostByModel]:
		rows = (
			await db.execute(
				text(
					"""
					SELECT
						model,
						provider,
						COALESCE(SUM(total_requests), 0) AS requests,
						COALESCE(SUM(total_prompt_tokens + total_completion_tokens), 0) AS tokens,
						COALESCE(SUM(total_cost_usd), 0) AS cost_usd
					FROM mv_daily_spend
					WHERE org_id = :org_id
					  AND day::date >= :since
					GROUP BY model, provider
					ORDER BY cost_usd DESC
					LIMIT 20
					"""
				),
				{"org_id": str(org_id), "since": since},
			)
		).mappings().all()
		return [
			CostByModel(
				model=str(row["model"]),
				provider=str(row["provider"]),
				requests=int(row["requests"] or 0),
				tokens=int(row["tokens"] or 0),
				cost_usd=float(Decimal(str(row["cost_usd"] or 0))),
			)
			for row in rows
		]

	async def _cost_by_user(
		self,
		db: AsyncSession,
		org_id: UUID,
		since: date,
	) -> list[CostByUser]:
		rows = (
			await db.execute(
				text(
					"""
					SELECT
						m.user_id,
						u.email,
						COALESCE(SUM(m.total_requests), 0) AS requests,
						COALESCE(SUM(m.total_prompt_tokens + m.total_completion_tokens), 0) AS tokens,
						COALESCE(SUM(m.total_cost_usd), 0) AS cost_usd
					FROM mv_daily_spend m
					JOIN users u ON u.id = m.user_id
					WHERE m.org_id = :org_id
					  AND u.org_id = :org_id
					  AND m.day::date >= :since
					GROUP BY m.user_id, u.email
					ORDER BY cost_usd DESC
					LIMIT 50
					"""
				),
				{"org_id": str(org_id), "since": since},
			)
		).mappings().all()
		return [
			CostByUser(
				user_id=row["user_id"],
				email=str(row["email"]),
				requests=int(row["requests"] or 0),
				tokens=int(row["tokens"] or 0),
				cost_usd=float(Decimal(str(row["cost_usd"] or 0))),
			)
			for row in rows
		]

	async def _daily_trend(
		self,
		db: AsyncSession,
		org_id: UUID,
		since: date,
	) -> list[DailyUsageTrend]:
		rows = (
			await db.execute(
				text(
					"""
					SELECT
						day::date AS date,
						COALESCE(SUM(total_requests), 0) AS requests,
						COALESCE(SUM(total_prompt_tokens + total_completion_tokens), 0) AS tokens,
						COALESCE(SUM(total_cost_usd), 0) AS cost_usd,
						COALESCE(AVG(avg_latency_ms), 0) AS avg_latency_ms
					FROM mv_daily_spend
					WHERE org_id = :org_id
					  AND day::date >= :since
					GROUP BY day::date
					ORDER BY day::date ASC
					"""
				),
				{"org_id": str(org_id), "since": since},
			)
		).mappings().all()
		return [
			DailyUsageTrend(
				date=row["date"].isoformat(),
				requests=int(row["requests"] or 0),
				tokens=int(row["tokens"] or 0),
				cost_usd=float(Decimal(str(row["cost_usd"] or 0))),
				avg_latency_ms=float(row["avg_latency_ms"] or 0),
			)
			for row in rows
		]

	async def get_request_logs(
		self,
		db: AsyncSession,
		org_id: UUID,
		page: int,
		page_size: int,
		model: str | None = None,
		status: str | None = None,
	) -> Page[RequestLogItem]:
		offset = (page - 1) * page_size
		params: dict[str, object] = {
			"org_id": str(org_id),
			"limit": page_size,
			"offset": offset,
		}
		filters = ["org_id = :org_id"]
		if model:
			filters.append("model = :model")
			params["model"] = model
		if status == "success":
			filters.append("status_code < 400")
		elif status == "error":
			filters.append("status_code >= 400")

		where_clause = " AND ".join(filters)

		total = int(
			(
				await db.execute(
					text(f"SELECT COUNT(*) AS total FROM request_logs WHERE {where_clause}"),
					params,
				)
			).mappings().one()["total"]
		)

		rows = (
			await db.execute(
				text(
					f"""
					SELECT
						id,
						created_at,
						model,
						provider,
						prompt_tokens,
						completion_tokens,
						total_tokens,
						cost_usd,
						latency_ms,
						ttft_ms,
						status_code,
						error_message
					FROM request_logs
					WHERE {where_clause}
					ORDER BY created_at DESC
					LIMIT :limit OFFSET :offset
					"""
				),
				params,
			)
		).mappings().all()

		items = [
			RequestLogItem(
				id=row["id"],
				created_at=row["created_at"],
				model=str(row["model"]),
				provider=str(row["provider"]),
				status="success" if int(row["status_code"] or 0) < 400 else "error",
				prompt_tokens=int(row["prompt_tokens"] or 0),
				completion_tokens=int(row["completion_tokens"] or 0),
				total_tokens=int(row["total_tokens"] or 0),
				cost_usd=float(Decimal(str(row["cost_usd"] or 0))),
				latency_ms=row["latency_ms"],
				ttft_ms=row["ttft_ms"],
				error_message=row["error_message"],
			)
			for row in rows
		]

		total_pages = ceil(total / page_size) if total > 0 else 1
		return Page[RequestLogItem](
			items=items,
			total=total,
			page=page,
			page_size=page_size,
			total_pages=total_pages,
		)


analytics_service = AnalyticsService()
