"""Request scores API — submit quality scores for experiment evaluation."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_session_org_id
from app.dependencies import CurrentUser, get_db
from app.models.request_log import RequestLog
from app.models.request_score import RequestScore
from app.schemas.request_score import RequestScoresSubmit, RequestScoresSubmitResponse

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

	experiment_id = None
	variant_id = None
	exp = log.request_metadata.get("experiment") if log.request_metadata else None
	if exp:
		exp_id = exp.get("experiment_id")
		var_id = exp.get("variant_id")
		if exp_id:
			experiment_id = UUID(exp_id)
		if var_id:
			variant_id = UUID(var_id)

	submitted = 0
	for item in payload.scores:
		stmt = insert(RequestScore).values(
			request_id=request_id,
			org_id=current_user.org_id,
			experiment_id=experiment_id,
			variant_id=variant_id,
			score_name=item.name,
			value=item.value,
		).on_conflict_do_update(
			index_elements=["request_id", "score_name"],
			set_={
				RequestScore.value: item.value,
				RequestScore.experiment_id: experiment_id,
				RequestScore.variant_id: variant_id,
			},
		)
		await db.execute(stmt)
		submitted += 1

	await db.commit()
	return RequestScoresSubmitResponse(submitted=submitted)
