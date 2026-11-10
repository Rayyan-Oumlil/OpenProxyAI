"""POST /v1/feedback — an application tells the gateway whether an answer was good (Phase 3, slice 1)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_session_org_id
from app.dependencies import ProxyAuth, get_db
from app.models.request_log import RequestLog
from app.schemas.request_score import FeedbackRequest, FeedbackResponse
from app.services import pii_detection
from app.services.score_service import ScoreWrite, record_scores

router = APIRouter(tags=["Feedback"])

LLM_PERMISSION = "proxy:llm"


def _refusal(status_code: int, error: str, detail: str) -> JSONResponse:
	"""Same body shape as the other /v1 routes: {"error", "detail"}."""
	return JSONResponse(status_code=status_code, content={"error": error, "detail": detail}, headers={"X-OpenProxyAI-Gateway-Error": "true"})


@router.post("/v1/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest, auth: ProxyAuth, db: AsyncSession = Depends(get_db)):
	"""Rate one answer. Sending the same ``score_name`` for the same request again replaces the earlier rating.

	The request must belong to the caller's organization; one that does not exist and one that belongs to another
	organization are indistinguishable (both 404), so a key cannot probe for ids. A comment is stripped of PII first.
	"""
	user, api_key = auth
	if LLM_PERMISSION not in (api_key.permissions or []):
		return _refusal(403, "missing_permission", f"This API key lacks the {LLM_PERMISSION} permission.")

	await set_session_org_id(db, user.org_id)
	request_log = await db.scalar(
		select(RequestLog).where(RequestLog.request_id == payload.request_id, RequestLog.org_id == user.org_id)
	)
	if request_log is None:
		return _refusal(404, "request_not_found", "No request with that id in this organization.")

	comment = pii_detection.redact(payload.comment) if payload.comment else None
	await record_scores(
		db,
		org_id=user.org_id,
		request_id=payload.request_id,
		request_log=request_log,
		scores=[ScoreWrite(payload.resolved_name, payload.resolved_value, comment)],
		source="api",
		user_id=user.id,
	)
	return FeedbackResponse(request_id=payload.request_id, score_name=payload.resolved_name, value=payload.resolved_value)
