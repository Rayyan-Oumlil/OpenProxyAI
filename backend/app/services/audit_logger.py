"""Async background task for logging LLM requests to PostgreSQL and Redis."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from redis.asyncio import Redis

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.request_log import RequestLog
from app.services.cost_tracker import cost_tracker_service


async def _fire_policy_webhook(
	org_id: uuid.UUID,
	request_id: uuid.UUID,
	policy_meta: dict,
	model: str,
	user_id: uuid.UUID,
) -> None:
	"""Fire-and-forget webhook for policy violation. Swallows all exceptions."""
	try:
		from app.models.organization import Organization as _Org
		from app.services import webhook_service

		async with AsyncSessionLocal() as _db:
			_org = await _db.get(_Org, org_id)
			if _org is not None:
				await webhook_service.dispatch_event(
					db=_db,
					org=_org,
					event_type="policy.violation",
					data={
						"request_id": str(request_id),
						"reason_code": policy_meta.get("reason_code"),
						"triggered_rules": policy_meta.get("triggered_rules", []),
						"model": model,
						"user_id": str(user_id),
						"detail": policy_meta.get("detail"),
					},
				)
	except Exception as exc:
		import logging as _logging
		_logging.getLogger(__name__).error(
			"policy.violation webhook failed for org %s request %s: %s",
			org_id, request_id, exc,
		)


async def _fire_anomaly_check(
	redis: Redis,
	org_id: uuid.UUID,
	user_id: uuid.UUID,
) -> None:
	"""Fire-and-forget cost anomaly check. Fetches org and delegates to CostTrackerService."""
	try:
		from app.models.organization import Organization as _Org

		async with AsyncSessionLocal() as _db:
			_org = await _db.get(_Org, org_id)
			if _org is not None:
				await cost_tracker_service.check_anomaly(
					redis=redis,
					org_id=str(org_id),
					user_id=str(user_id) if user_id else None,
					db_session=_db,
					org=_org,
				)
	except Exception as exc:
		import logging as _logging
		_logging.getLogger(__name__).warning(
			"Cost anomaly check failed for org %s: %s", org_id, exc,
		)


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
	labels: dict[str, str] | None = None,
	team_id: uuid.UUID | None = None,
) -> None:
	total_tokens = prompt_tokens + completion_tokens
	metadata = {**(request_metadata or {})}
	if labels:
		metadata = {**metadata, "labels": labels}
	if team_id is not None:
		metadata = {**metadata, "team_id": str(team_id)}
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
			request_metadata=metadata,
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

	if team_id is not None:
		month_key = datetime.now(UTC).strftime("%Y-%m")
		team_usd_key = f"rl:usd:team:{team_id}:{month_key}"
		await redis.incrbyfloat(team_usd_key, float(cost_usd))
		await redis.expire(team_usd_key, 60 * 24 * 3600)  # 60 days

	await cost_tracker_service.alert_at_threshold(
		redis=redis,
		org_id=org_id,
		current_spend=Decimal(str(org_spend or "0")),
		budget_daily_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)),
	)

	# Webhook — policy violation events
	if status_code == 403:
		policy_meta = (request_metadata or {}).get("policy", {})
		if policy_meta.get("action") == "block":
			import asyncio as _asyncio
			_asyncio.create_task(_fire_policy_webhook(
				org_id=org_id,
				request_id=request_id,
				policy_meta=policy_meta,
				model=model,
				user_id=user_id,
			))

	# Optional Langfuse tracing (fire-and-forget)
	from app.services import langfuse_service
	if langfuse_service.is_enabled():
		import asyncio
		policy_meta = (request_metadata or {}).get("policy", {})
		asyncio.create_task(langfuse_service.send_trace(
			request_id=str(request_id),
			org_id=str(org_id),
			user_id=str(user_id),
			model=model,
			provider=provider,
			prompt_tokens=prompt_tokens or 0,
			completion_tokens=completion_tokens or 0,
			cost_usd=float(cost_usd or 0),
			latency_ms=latency_ms,
			ttft_ms=ttft_ms,
			status_code=status_code,
			policy_action=policy_meta.get("action"),
			error_message=error_message,
		))

	# Fire cost anomaly check (Phase 3)
	import asyncio as _asyncio
	_asyncio.create_task(_fire_anomaly_check(
		redis=redis,
		org_id=org_id,
		user_id=user_id,
	))

	# ClickHouse dual-write (Phase 3 — fire-and-forget)
	import asyncio as _ch_asyncio
	from app.services import clickhouse_service
	if clickhouse_service.is_enabled():
		ch_policy_meta = (request_metadata or {}).get("policy", {})
		_ch_asyncio.create_task(clickhouse_service.write_log({
			"request_id": request_id,
			"org_id": org_id,
			"user_id": user_id,
			"api_key_id": api_key_id,
			"model": model,
			"provider": provider,
			"prompt_tokens": prompt_tokens or 0,
			"completion_tokens": completion_tokens or 0,
			"total_tokens": total_tokens,
			"cost_usd": float(cost_usd or 0),
			"latency_ms": latency_ms,
			"ttft_ms": ttft_ms or 0,
			"status_code": status_code,
			"policy_action": ch_policy_meta.get("action", ""),
			"created_at": datetime.now(UTC),
		}))

	# Prometheus metrics
	from app.services.metrics_service import record_request as _record_metrics

	if settings.PROMETHEUS_ENABLED:
		prom_policy_meta = (request_metadata or {}).get("policy", {})
		limit_type = None
		if error_message and error_message.startswith("rate_limited:"):
			limit_type = error_message.split(":", 1)[1]
		_record_metrics(
			model=model,
			provider=provider,
			status_code=status_code,
			org_id=str(org_id),
			latency_ms=latency_ms,
			ttft_ms=ttft_ms,
			prompt_tokens=prompt_tokens or 0,
			completion_tokens=completion_tokens or 0,
			cost_usd=float(cost_usd or 0),
			policy_action=prom_policy_meta.get("action"),
			policy_reason_code=prom_policy_meta.get("reason_code"),
			limit_type=limit_type,
		)

