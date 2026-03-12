"""Analytics endpoints — overview and request log queries scoped by organization."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.schemas.analytics import AnalyticsResponse
from app.schemas.logs import Page, RequestLogItem
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
	db: AsyncSession = Depends(get_db),
) -> Page[RequestLogItem]:
	return await analytics_service.get_request_logs(
		db=db,
		org_id=current_user.org_id,
		page=page,
		page_size=page_size,
		model=model,
		status=status,
	)
