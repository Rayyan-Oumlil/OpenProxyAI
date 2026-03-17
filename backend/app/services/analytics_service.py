"""Analytics service querying mv_daily_spend and request logs with org isolation."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_log import RequestLog

from app.schemas.analytics import (
	AnalyticsResponse,
	CostByModel,
	CostByUser,
	DailyUsageTrend,
	PolicyActionStat,
	PolicyAnalyticsResponse,
	PolicyReasonStat,
	UsageOverview,
)
from app.schemas.logs import Page, RequestLogDetail, RequestLogItem
from app.schemas.reconcile import (
	ProviderRecord,
	ReconcileReport,
	ReconcileRowDelta,
	ReconcileSummary,
)


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
						COALESCE(AVG(ttft_ms), 0) AS avg_ttft_ms,
						COALESCE(
							SUM(
								CASE
									WHEN request_metadata->'policy'->>'action' = 'block' THEN 1
									ELSE 0
								END
							),
							0
						) AS policy_blocked_requests,
						COALESCE(
							SUM(
								CASE
									WHEN request_metadata->'policy'->>'action' IN ('block', 'log_only') THEN 1
									ELSE 0
								END
							),
							0
						) AS policy_flagged_requests
					FROM request_logs
					WHERE org_id = :org_id
					  AND created_at::date >= :since
					  AND archived_at IS NULL
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
			policy_blocked_requests=int(log_row["policy_blocked_requests"] or 0),
			policy_flagged_requests=int(log_row["policy_flagged_requests"] or 0),
			total_tokens=int(mv_row["total_tokens"] or 0),
			total_cost_usd=float(Decimal(str(mv_row["total_cost_usd"] or 0))),
			avg_latency_ms=float(mv_row["avg_latency_ms"] or 0),
			avg_ttft_ms=float(log_row["avg_ttft_ms"] or 0),
		)

	async def get_policy_summary(
		self,
		db: AsyncSession,
		org_id: UUID,
		period_days: int = 30,
	) -> PolicyAnalyticsResponse:
		since = datetime.now(UTC).date() - timedelta(days=period_days - 1)
		action_rows = (
			await db.execute(
				text(
					"""
					SELECT
						request_metadata->'policy'->>'action' AS action,
						COUNT(*) AS count
					FROM request_logs
					WHERE org_id = :org_id
					  AND created_at::date >= :since
					  AND archived_at IS NULL
					  AND request_metadata->'policy'->>'action' IS NOT NULL
					GROUP BY request_metadata->'policy'->>'action'
					ORDER BY count DESC
					"""
				),
				{"org_id": str(org_id), "since": since},
			)
		).mappings().all()

		reason_rows = (
			await db.execute(
				text(
					"""
					SELECT
						request_metadata->'policy'->>'reason_code' AS reason_code,
						COALESCE(request_metadata->'policy'->>'action', 'unknown') AS action,
						COUNT(*) AS count
					FROM request_logs
					WHERE org_id = :org_id
					  AND created_at::date >= :since
					  AND archived_at IS NULL
					  AND request_metadata->'policy'->>'reason_code' IS NOT NULL
					GROUP BY request_metadata->'policy'->>'reason_code', request_metadata->'policy'->>'action'
					ORDER BY count DESC
					LIMIT 20
					"""
				),
				{"org_id": str(org_id), "since": since},
			)
		).mappings().all()

		by_action = [
			PolicyActionStat(action=str(row["action"]), count=int(row["count"] or 0))
			for row in action_rows
		]
		by_reason = [
			PolicyReasonStat(
				reason_code=str(row["reason_code"]),
				action=str(row["action"]),
				count=int(row["count"] or 0),
			)
			for row in reason_rows
		]
		total_policy_events = sum(item.count for item in by_action)

		return PolicyAnalyticsResponse(
			period_days=period_days,
			total_policy_events=total_policy_events,
			by_action=by_action,
			by_reason=by_reason,
			generated_at=datetime.now(UTC),
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
		policy_action: str | None = None,
		policy_reason: str | None = None,
		include_archived: bool = False,
		label_key: str | None = None,
		label_value: str | None = None,
	) -> Page[RequestLogItem]:
		"""Return a paginated, filtered list of request logs for the given org.

		All filter values are passed through SQLAlchemy ORM bound parameters —
		no user-supplied strings are ever interpolated into the SQL text.
		"""
		offset = (page - 1) * page_size

		conditions: list[Any] = [RequestLog.org_id == org_id]
		if not include_archived:
			conditions.append(RequestLog.archived_at.is_(None))
		if model:
			conditions.append(RequestLog.model == model)
		if status == "success":
			conditions.append(RequestLog.status_code < 400)
		elif status == "error":
			conditions.append(RequestLog.status_code >= 400)
		if policy_action:
			conditions.append(
				RequestLog.request_metadata["policy"]["action"].astext == policy_action
			)
		if policy_reason:
			conditions.append(
				RequestLog.request_metadata["policy"]["reason_code"].astext.ilike(
					f"%{policy_reason}%"
				)
			)
		if label_key is not None and label_value is not None:
			conditions.append(
				RequestLog.request_metadata["labels"][label_key].as_string() == label_value
			)

		where = and_(*conditions)

		total = (
			await db.execute(select(func.count()).select_from(RequestLog).where(where))
		).scalar_one()

		rows = (
			await db.execute(
				select(
					RequestLog.id,
					RequestLog.created_at,
					RequestLog.model,
					RequestLog.provider,
					RequestLog.prompt_tokens,
					RequestLog.completion_tokens,
					RequestLog.total_tokens,
					RequestLog.cost_usd,
					RequestLog.latency_ms,
					RequestLog.ttft_ms,
					RequestLog.status_code,
					RequestLog.error_message,
					RequestLog.request_metadata,
				)
				.where(where)
				.order_by(RequestLog.created_at.desc())
				.limit(page_size)
				.offset(offset)
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
				policy_action=(row["request_metadata"] or {}).get("policy", {}).get("action"),
				policy_reason=(row["request_metadata"] or {}).get("policy", {}).get("reason_code"),
				policy_triggered_rules=(row["request_metadata"] or {}).get("policy", {}).get("triggered_rules"),
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

	async def get_log_detail(
		self,
		db: AsyncSession,
		org_id: UUID,
		log_id: UUID,
	) -> RequestLogDetail | None:
		"""Return full detail for a single log entry, or None if not found / not owned by org."""
		row = (
			await db.execute(
				select(RequestLog).where(
					RequestLog.id == log_id,
					RequestLog.org_id == org_id,
				)
			)
		).scalar_one_or_none()

		if row is None:
			return None

		metadata = row.request_metadata or {}
		policy = metadata.get("policy", {})
		return RequestLogDetail(
			id=row.id,
			request_id=row.request_id,
			user_id=row.user_id,
			api_key_id=row.api_key_id,
			created_at=row.created_at,
			model=row.model,
			provider=row.provider,
			status="success" if int(row.status_code or 0) < 400 else "error",
			status_code=int(row.status_code),
			prompt_tokens=int(row.prompt_tokens or 0),
			completion_tokens=int(row.completion_tokens or 0),
			total_tokens=int(row.total_tokens or 0),
			cost_usd=float(Decimal(str(row.cost_usd or 0))),
			latency_ms=row.latency_ms,
			ttft_ms=row.ttft_ms,
			error_message=row.error_message,
			policy_action=policy.get("action"),
			policy_reason=policy.get("reason_code"),
			policy_triggered_rules=policy.get("triggered_rules"),
			request_metadata=metadata,
		)

	@staticmethod
	def resolve_window(period_days: int, start_date: date | None, end_date: date | None) -> tuple[date, date]:
		if start_date is not None and end_date is not None:
			if start_date > end_date:
				raise ValueError("start_date must be before or equal to end_date")
			return start_date, end_date
		if start_date is not None:
			return start_date, start_date
		if end_date is not None:
			return end_date, end_date
		window_end = datetime.now(UTC).date()
		window_start = window_end - timedelta(days=period_days - 1)
		return window_start, window_end

	async def get_policy_events(
		self,
		db: AsyncSession,
		org_id: UUID,
		period_days: int = 30,
		start_date: date | None = None,
		end_date: date | None = None,
		action: str | None = None,
		reason_code: str | None = None,
	) -> list[dict[str, Any]]:
		window_start, window_end = self.resolve_window(period_days, start_date, end_date)
		filters = [
			"org_id = :org_id",
			"created_at::date >= :window_start",
			"created_at::date <= :window_end",
			"archived_at IS NULL",
			"request_metadata->'policy'->>'action' IS NOT NULL",
		]
		params: dict[str, object] = {
			"org_id": str(org_id),
			"window_start": window_start,
			"window_end": window_end,
		}
		if action:
			filters.append("request_metadata->'policy'->>'action' = :action")
			params["action"] = action
		if reason_code:
			filters.append("request_metadata->'policy'->>'reason_code' ILIKE :reason_code")
			params["reason_code"] = f"%{reason_code}%"

		_EXPORT_HARD_LIMIT = 10_000

		where_clause = " AND ".join(filters)
		rows = (
			await db.execute(
				text(
					f"""
					SELECT
						id,
						request_id,
						created_at,
						model,
						provider,
						status_code,
						request_metadata->'policy'->>'action' AS policy_action,
						request_metadata->'policy'->>'reason_code' AS policy_reason,
						request_metadata->'policy'->'triggered_rules' AS policy_triggered_rules
					FROM request_logs
					WHERE {where_clause}
					ORDER BY created_at DESC
					LIMIT {_EXPORT_HARD_LIMIT + 1}
					"""
				),
				params,
			)
		).mappings().all()

		# Detect truncation before capping at the hard limit.
		truncated = len(rows) > _EXPORT_HARD_LIMIT
		if truncated:
			rows = rows[:_EXPORT_HARD_LIMIT]

		events: list[dict[str, Any]] = []
		for row in rows:
			rules_raw = row.get("policy_triggered_rules")
			rules = rules_raw if isinstance(rules_raw, list) else []
			events.append(
				{
					"id": str(row["id"]),
					"request_id": str(row["request_id"]),
					"created_at": row["created_at"].isoformat(),
					"model": str(row["model"]),
					"provider": str(row["provider"]),
					"status_code": int(row["status_code"] or 0),
					"policy_action": row.get("policy_action"),
					"policy_reason": row.get("policy_reason"),
					"policy_triggered_rules": rules,
				}
			)
		return events, truncated


	async def reconcile_with_provider(
		self,
		db: AsyncSession,
		org_id: UUID,
		provider: str,
		records: list[ProviderRecord],
	) -> ReconcileReport:
		"""Compare gateway aggregates against provider export records for the same date range.

		Returns a row-level delta report plus totals. All deltas are gateway minus provider,
		so a positive delta means the gateway counted more than the provider did.
		"""
		# Build provider lookup: (date_str, model) -> stats dict
		prov: dict[tuple[str, str], dict[str, Any]] = {}
		for r in records:
			key = (r.date, r.model)
			if key in prov:
				existing = prov[key]
				prov[key] = {
					"requests": existing["requests"] + r.requests,
					"input_tokens": existing["input_tokens"] + r.input_tokens,
					"output_tokens": existing["output_tokens"] + r.output_tokens,
					"cost_usd": existing["cost_usd"] + r.cost_usd,
				}
			else:
				prov[key] = {
					"requests": r.requests,
					"input_tokens": r.input_tokens,
					"output_tokens": r.output_tokens,
					"cost_usd": r.cost_usd,
				}

		all_dates = [r.date for r in records]
		period_start = min(all_dates)
		period_end = max(all_dates)

		# Query gateway aggregates for this provider + date range
		gw_rows = (
			await db.execute(
				text(
					"""
					SELECT
						day::date AS date,
						model,
						COALESCE(SUM(total_requests), 0) AS requests,
						COALESCE(SUM(total_prompt_tokens), 0) AS input_tokens,
						COALESCE(SUM(total_completion_tokens), 0) AS output_tokens,
						COALESCE(SUM(total_cost_usd), 0) AS cost_usd
					FROM mv_daily_spend
					WHERE org_id = :org_id
					  AND provider = :provider
					  AND day::date >= :period_start
					  AND day::date <= :period_end
					GROUP BY day::date, model
					ORDER BY day::date, model
					"""
				),
				{
					"org_id": str(org_id),
					"provider": provider,
					"period_start": period_start,
					"period_end": period_end,
				},
			)
		).mappings().all()

		# Build gateway lookup: (date_str, model) -> stats dict
		gw: dict[tuple[str, str], dict[str, Any]] = {}
		for row in gw_rows:
			key = (row["date"].isoformat(), str(row["model"]))
			gw[key] = {
				"requests": int(row["requests"]),
				"input_tokens": int(row["input_tokens"]),
				"output_tokens": int(row["output_tokens"]),
				"cost_usd": float(Decimal(str(row["cost_usd"]))),
			}

		def _pct(gateway_val: float, provider_val: float) -> float | None:
			if provider_val == 0:
				return None
			return round((gateway_val - provider_val) / provider_val * 100, 2)

		_zero: dict[str, Any] = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
		all_keys = sorted(set(prov.keys()) | set(gw.keys()))

		delta_rows: list[ReconcileRowDelta] = []
		for date_str, model in all_keys:
			key = (date_str, model)
			g = gw.get(key, _zero)
			p = prov.get(key, _zero)
			delta_rows.append(
				ReconcileRowDelta(
					date=date_str,
					model=model,
					gateway_requests=g["requests"],
					provider_requests=p["requests"],
					delta_requests=g["requests"] - p["requests"],
					pct_delta_requests=_pct(g["requests"], p["requests"]),
					gateway_input_tokens=g["input_tokens"],
					provider_input_tokens=p["input_tokens"],
					delta_input_tokens=g["input_tokens"] - p["input_tokens"],
					pct_delta_input_tokens=_pct(g["input_tokens"], p["input_tokens"]),
					gateway_output_tokens=g["output_tokens"],
					provider_output_tokens=p["output_tokens"],
					delta_output_tokens=g["output_tokens"] - p["output_tokens"],
					pct_delta_output_tokens=_pct(g["output_tokens"], p["output_tokens"]),
					gateway_cost_usd=g["cost_usd"],
					provider_cost_usd=p["cost_usd"],
					delta_cost_usd=round(g["cost_usd"] - p["cost_usd"], 6),
					pct_delta_cost_usd=_pct(g["cost_usd"], p["cost_usd"]),
				)
			)

		total_gw_req = sum(r.gateway_requests for r in delta_rows)
		total_pr_req = sum(r.provider_requests for r in delta_rows)
		total_gw_in = sum(r.gateway_input_tokens for r in delta_rows)
		total_pr_in = sum(r.provider_input_tokens for r in delta_rows)
		total_gw_out = sum(r.gateway_output_tokens for r in delta_rows)
		total_pr_out = sum(r.provider_output_tokens for r in delta_rows)
		total_gw_cost = sum(r.gateway_cost_usd for r in delta_rows)
		total_pr_cost = sum(r.provider_cost_usd for r in delta_rows)

		mismatch_count = sum(
			1
			for r in delta_rows
			if r.delta_requests != 0 or r.delta_input_tokens != 0 or r.delta_output_tokens != 0
		)

		return ReconcileReport(
			provider=provider,
			period_start=period_start,
			period_end=period_end,
			total_rows=len(delta_rows),
			mismatch_rows=mismatch_count,
			rows=delta_rows,
			summary=ReconcileSummary(
				total_gateway_requests=total_gw_req,
				total_provider_requests=total_pr_req,
				total_delta_requests=total_gw_req - total_pr_req,
				total_gateway_input_tokens=total_gw_in,
				total_provider_input_tokens=total_pr_in,
				total_delta_input_tokens=total_gw_in - total_pr_in,
				total_gateway_output_tokens=total_gw_out,
				total_provider_output_tokens=total_pr_out,
				total_delta_output_tokens=total_gw_out - total_pr_out,
				total_gateway_cost_usd=round(total_gw_cost, 6),
				total_provider_cost_usd=round(total_pr_cost, 6),
				total_delta_cost_usd=round(total_gw_cost - total_pr_cost, 6),
			),
			generated_at=datetime.now(UTC),
		)


analytics_service = AnalyticsService()
