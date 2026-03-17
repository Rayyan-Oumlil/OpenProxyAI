"""Analytics endpoints — overview and request log queries scoped by organization."""

import csv
import io
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.schemas.analytics import AnalyticsResponse, PolicyAnalyticsResponse
from app.schemas.logs import Page, RequestLogDetail, RequestLogItem
from app.schemas.reconcile import ReconcileReport, ReconcileRequest
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/overview", response_model=AnalyticsResponse)
async def get_analytics_overview(
	current_user: CurrentUser,
	period_days: int = Query(default=30, ge=1, le=90),
	db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
	return await analytics_service.get_overview(
		db=db,
		org_id=current_user.org_id,
		period_days=period_days,
	)


@router.get("/logs", response_model=Page[RequestLogItem])
async def get_request_logs(
	current_user: CurrentUser,
	page: int = Query(default=1, ge=1),
	page_size: int = Query(default=50, ge=1, le=200),
	model: str | None = Query(default=None),
	status: str | None = Query(default=None, pattern="^(success|error)$"),
	policy_action: str | None = Query(default=None, pattern="^(allow|log_only|block)$"),
	policy_reason: str | None = Query(default=None, min_length=1, max_length=120),
	include_archived: bool = Query(default=False),
	label_key: str | None = Query(default=None, min_length=1, max_length=64),
	label_value: str | None = Query(default=None, min_length=1, max_length=64),
	db: AsyncSession = Depends(get_db),
) -> Page[RequestLogItem]:
	return await analytics_service.get_request_logs(
		db=db,
		org_id=current_user.org_id,
		page=page,
		page_size=page_size,
		model=model,
		status=status,
		policy_action=policy_action,
		policy_reason=policy_reason,
		include_archived=include_archived,
		label_key=label_key,
		label_value=label_value,
	)


@router.get("/logs/{log_id}", response_model=RequestLogDetail)
async def get_log_detail(
	log_id: uuid.UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> RequestLogDetail:
	detail = await analytics_service.get_log_detail(
		db=db,
		org_id=current_user.org_id,
		log_id=log_id,
	)
	if detail is None:
		raise HTTPException(status_code=404, detail="Log entry not found")
	return detail


@router.get("/policy", response_model=PolicyAnalyticsResponse)
async def get_policy_analytics(
	current_user: CurrentUser,
	period_days: int = Query(default=30, ge=1, le=90),
	db: AsyncSession = Depends(get_db),
) -> PolicyAnalyticsResponse:
	return await analytics_service.get_policy_summary(
		db=db,
		org_id=current_user.org_id,
		period_days=period_days,
	)


@router.get("/policy/export")
async def export_policy_events(
	current_user: CurrentUser,
	format: Literal["json", "csv"] = Query(default="json"),
	period_days: int = Query(default=30, ge=1, le=365),
	start_date: date | None = Query(default=None),
	end_date: date | None = Query(default=None),
	action: str | None = Query(default=None, pattern="^(allow|log_only|block)$"),
	reason_code: str | None = Query(default=None, min_length=1, max_length=120),
	db: AsyncSession = Depends(get_db),
):
	try:
		events, truncated = await analytics_service.get_policy_events(
			db=db,
			org_id=current_user.org_id,
			period_days=period_days,
			start_date=start_date,
			end_date=end_date,
			action=action,
			reason_code=reason_code,
		)
	except ValueError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc

	extra_headers: dict[str, str] = {}
	if truncated:
		extra_headers["X-Result-Truncated"] = "true"

	if format == "csv":
		buffer = io.StringIO()
		writer = csv.DictWriter(
			buffer,
			fieldnames=[
				"id",
				"request_id",
				"created_at",
				"model",
				"provider",
				"status_code",
				"policy_action",
				"policy_reason",
				"policy_triggered_rules",
			],
		)
		writer.writeheader()
		for event in events:
			row = dict(event)
			row["policy_triggered_rules"] = ";".join(event.get("policy_triggered_rules") or [])
			writer.writerow(row)

		return Response(
			content=buffer.getvalue(),
			media_type="text/csv",
			headers={"Content-Disposition": "attachment; filename=policy-events.csv", **extra_headers},
		)

	return JSONResponse(
		content={"items": events, "total": len(events)},
		headers={"Content-Disposition": "attachment; filename=policy-events.json", **extra_headers},
	)


@router.post("/reconcile", response_model=ReconcileReport)
async def reconcile_usage(
	current_user: CurrentUser,
	body: ReconcileRequest,
	db: AsyncSession = Depends(get_db),
) -> ReconcileReport:
	"""Compare provider usage export against gateway aggregates for the same date range.

	All deltas are gateway minus provider. Positive delta = gateway counted more.
	Submit provider records as JSON; get back a row-level mismatch report.
	"""
	if not body.records:
		raise HTTPException(status_code=422, detail="records must not be empty")
	return await analytics_service.reconcile_with_provider(
		db=db,
		org_id=current_user.org_id,
		provider=body.provider,
		records=body.records,
	)
