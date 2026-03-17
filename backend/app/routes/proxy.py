"""LLM proxy endpoints — POST /v1/chat/completions, POST /v1/embeddings."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import ProxyAuth, get_db, get_redis, get_request_id
from app.schemas.chat import ChatCompletionRequest, EmbeddingRequest
from app.services.llm_service import llm_service

router = APIRouter(tags=["Proxy"])


@router.post("/v1/chat/completions")
async def chat_completions(
	request: ChatCompletionRequest,
	http_request: Request,
	background_tasks: BackgroundTasks,
	auth: ProxyAuth,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
	request_id: str = Depends(get_request_id),
):
	user, api_key = auth
	try:
		normalized_request_id = uuid.UUID(request_id)
	except (TypeError, ValueError):
		normalized_request_id = uuid.uuid4()
	try:
		return await llm_service.chat_completion(
			request=request,
			db=db,
			redis=redis,
			user=user,
			api_key=api_key,
			request_id=normalized_request_id,
			background_tasks=background_tasks,
			http_request=http_request,
		)
	except HTTPException as exc:
		detail = exc.detail if isinstance(exc.detail, dict) else {"error": "gateway_error", "detail": str(exc.detail)}
		detail.setdefault("error", "gateway_error")
		detail.setdefault("detail", "Gateway request failed")
		headers = {"X-OpenProxyAI-Gateway-Error": "true"}
		if exc.headers:
			headers.update(exc.headers)
		return JSONResponse(
			status_code=exc.status_code,
			content=detail,
			headers=headers,
		)


@router.post("/v1/embeddings")
async def embeddings(
	request: EmbeddingRequest,
	http_request: Request,
	background_tasks: BackgroundTasks,
	auth: ProxyAuth,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
	request_id: str = Depends(get_request_id),
):
	user, api_key = auth
	try:
		normalized_request_id = uuid.UUID(request_id)
	except (TypeError, ValueError):
		normalized_request_id = uuid.uuid4()
	try:
		return await llm_service.embedding(
			request=request,
			db=db,
			redis=redis,
			user=user,
			api_key=api_key,
			request_id=normalized_request_id,
			background_tasks=background_tasks,
			http_request=http_request,
		)
	except HTTPException as exc:
		detail = exc.detail if isinstance(exc.detail, dict) else {"error": "gateway_error", "detail": str(exc.detail)}
		detail.setdefault("error", "gateway_error")
		detail.setdefault("detail", "Gateway request failed")
		headers = {"X-OpenProxyAI-Gateway-Error": "true"}
		if exc.headers:
			headers.update(exc.headers)
		return JSONResponse(
			status_code=exc.status_code,
			content=detail,
			headers=headers,
		)

