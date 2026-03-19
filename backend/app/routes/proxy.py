"""LLM proxy endpoints — POST /v1/chat/completions, POST /v1/embeddings, GET /v1/models."""

import fnmatch
import uuid

import litellm
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import ProxyAuth, get_db, get_redis, get_request_id
from app.models.llm_provider_key import LLMProviderKey
from app.schemas.chat import ChatCompletionRequest, EmbeddingRequest
from app.schemas.models import ModelListResponse, ModelResponse
from app.services.llm_service import llm_service

router = APIRouter(tags=["Proxy"])


def _expand_models_for_provider_key(
	provider: str,
	model_patterns: list[str] | None,
) -> set[str]:
	"""Expand model_patterns into concrete model IDs using LiteLLM's local registry.

	If model_patterns is null/empty, include all models for the provider.
	Returns set of model IDs in provider/model format.
	"""
	all_models: list[str] = litellm.models_by_provider.get(provider, [])
	if not all_models:
		return set()

	if not model_patterns:
		return {f"{provider}/{m}" for m in all_models}

	matched: set[str] = set()
	for model in all_models:
		if any(fnmatch.fnmatch(model, pat) for pat in model_patterns):
			matched.add(f"{provider}/{model}")
	return matched


@router.get("/v1/models", response_model=ModelListResponse)
async def list_models(
	auth: ProxyAuth,
	db: AsyncSession = Depends(get_db),
):
	"""Return OpenAI-compatible model list aggregated from the org's provider keys."""
	_user, api_key = auth
	org_id = api_key.org_id

	rows = await db.scalars(
		select(LLMProviderKey).where(
			LLMProviderKey.org_id == org_id,
			LLMProviderKey.is_active.is_(True),
		)
	)
	keys = list(rows.all())

	model_ids: set[str] = set()
	for key in keys:
		patterns: list[str] | None = key.model_patterns
		model_ids |= _expand_models_for_provider_key(key.provider, patterns)

	sorted_ids = sorted(model_ids)
	data = [
		ModelResponse(
			id=mid,
			object="model",
			owned_by=mid.split("/", 1)[0],
		)
		for mid in sorted_ids
	]
	return ModelListResponse(object="list", data=data)


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

