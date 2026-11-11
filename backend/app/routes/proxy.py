"""LLM proxy endpoints — POST /v1/chat/completions, POST /v1/embeddings, GET /v1/models."""

import fnmatch
import uuid

import litellm
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import ProxyAuth, get_db, get_redis, get_request_id
from app.models.llm_provider_key import LLMProviderKey
from app.schemas.chat import ChatCompletionRequest, EmbeddingRequest
from app.schemas.models import ModelListResponse, ModelResponse
from app.services.llm_service import llm_service
from app.schemas.modalities import MAX_AUDIO_BYTES, ImageRequest, RerankRequest, ResponsesRequest, SpeechRequest, TranscriptionRequest
from app.services.modalities import EMBEDDINGS, IMAGES, RERANK, RESPONSES, TRANSCRIPTION, speech_modality
from app.services.modality_pipeline import run_modality

router = APIRouter(tags=["Proxy"])


def _proxy_error_response(exc: HTTPException) -> JSONResponse:
    """Normalize HTTPException detail and return JSONResponse with gateway header."""
    detail = (
        dict(exc.detail)
        if isinstance(exc.detail, dict)
        else {"error": "gateway_error", "detail": str(exc.detail)}
    )
    detail.setdefault("error", "gateway_error")
    detail.setdefault("detail", "Gateway request failed")
    headers = {"X-OpenProxyAI-Gateway-Error": "true"}
    if exc.headers:
        headers.update(exc.headers)
    return JSONResponse(status_code=exc.status_code, content=detail, headers=headers)


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
        return _proxy_error_response(exc)


async def _serve(modality, request, http_request, background_tasks, auth, db, redis, request_id):
    """Every non-chat endpoint is this: the shared pipeline with the endpoint's own modality."""
    user, api_key = auth
    try:
        normalized_request_id = uuid.UUID(request_id)
    except (TypeError, ValueError):
        normalized_request_id = uuid.uuid4()
    try:
        return await run_modality(
            modality,
            request,
            db=db,
            redis=redis,
            user=user,
            api_key=api_key,
            request_id=normalized_request_id,
            background_tasks=background_tasks,
            http_request=http_request,
        )
    except HTTPException as exc:
        return _proxy_error_response(exc)


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
    return await _serve(EMBEDDINGS, request, http_request, background_tasks, auth, db, redis, request_id)


@router.post("/v1/rerank")
async def rerank(
    request: RerankRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth: ProxyAuth,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    request_id: str = Depends(get_request_id),
):
    return await _serve(RERANK, request, http_request, background_tasks, auth, db, redis, request_id)


@router.post("/v1/images/generations")
async def image_generations(
    request: ImageRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth: ProxyAuth,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    request_id: str = Depends(get_request_id),
):
    return await _serve(IMAGES, request, http_request, background_tasks, auth, db, redis, request_id)


@router.post("/v1/audio/speech")
async def audio_speech(
    request: SpeechRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth: ProxyAuth,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    request_id: str = Depends(get_request_id),
):
    return await _serve(speech_modality(request), request, http_request, background_tasks, auth, db, redis, request_id)


_MULTIPART_OVERHEAD_BYTES = 64 * 1024  # form fields and boundaries around the file


def _upload_error(status_code: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error, "detail": detail}, headers={"X-OpenProxyAI-Gateway-Error": "true"})


@router.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth: ProxyAuth,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    request_id: str = Depends(get_request_id),
):
    """Multipart upload. The form is read by hand, after authentication, because the framework would spool a body of any size to disk
    before a handler could refuse it: the declared length is checked first, and the file itself is checked again once read."""
    declared = http_request.headers.get("content-length")
    if declared is None or not declared.isdigit():
        return _upload_error(411, "length_required", "A Content-Length header is required for uploads.")
    if int(declared) > MAX_AUDIO_BYTES + _MULTIPART_OVERHEAD_BYTES:
        return _upload_error(413, "file_too_large", f"Audio files can be at most {MAX_AUDIO_BYTES} bytes.")
    form = await http_request.form(max_files=1, max_fields=10)
    upload = form.get("file")
    if not isinstance(upload, UploadFile) or not isinstance(form.get("model"), str):
        return _upload_error(422, "invalid_request", "Send multipart form data with a model and a file.")
    data = await upload.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        return _upload_error(413, "file_too_large", f"Audio files can be at most {MAX_AUDIO_BYTES} bytes.")

    def field(name: str):
        value = form.get(name)
        return value if isinstance(value, str) and value != "" else None

    temperature = field("temperature")
    try:
        request = TranscriptionRequest(
            model=form["model"], filename=upload.filename or "", data=data, language=field("language"), prompt=field("prompt"),
            response_format=field("response_format") or "json", temperature=float(temperature) if temperature is not None else None,
        )
    except (ValidationError, ValueError) as exc:
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else "temperature must be a number"
        return _upload_error(422, "invalid_request", message)
    return await _serve(TRANSCRIPTION, request, http_request, background_tasks, auth, db, redis, request_id)


@router.post("/v1/responses")
async def responses(
    request: ResponsesRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth: ProxyAuth,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    request_id: str = Depends(get_request_id),
):
    return await _serve(RESPONSES, request, http_request, background_tasks, auth, db, redis, request_id)
