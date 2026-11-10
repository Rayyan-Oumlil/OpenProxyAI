"""Request scores API — submit quality scores for experiment evaluation."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_session_org_id
from app.dependencies import CurrentUser, get_db
from app.models.request_log import RequestLog
from app.schemas.request_score import RequestScoresSubmit, RequestScoresSubmitResponse
from app.services.score_service import ScoreWrite, record_scores

router = APIRouter(prefix="/api/v1/requests", tags=["Requests"])


@router.post("/{request_id}/scores", response_model=RequestScoresSubmitResponse)
async def submit_request_scores(
	request_id: UUID,
	payload: RequestScoresSubmit,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> RequestScoresSubmitResponse:
	"""Submit quality scores for a request. Request must exist and belong to the org."""
	await set_session_org_id(db, current_user.org_id)

	# Verify request exists and belongs to org
	log = await db.scalar(
		select(RequestLog).where(
			RequestLog.request_id == request_id,
			RequestLog.org_id == current_user.org_id,
		)
	)
	if log is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Request not found",
		)

	submitted = await record_scores(
		db,
		org_id=current_user.org_id,
		request_id=request_id,
		request_log=log,
		scores=[ScoreWrite(item.name, item.value) for item in payload.scores],
		source="console",
		user_id=current_user.id,
	)
	return RequestScoresSubmitResponse(submitted=submitted)
