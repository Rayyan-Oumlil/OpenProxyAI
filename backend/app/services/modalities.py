"""The endpoint-specific parts of each non-chat modality (Phase 5). The sequence they all run through is in ``modality_pipeline``."""

from __future__ import annotations

import io
from typing import Any

from fastapi.responses import Response

from app.schemas.chat import EmbeddingRequest
from app.schemas.modalities import SPEECH_FORMATS, ImageRequest, RerankRequest, ResponsesRequest, SpeechRequest, TranscriptionRequest
from app.services import llm_service as ls
from app.services.llm_service import with_endpoint
from app.services.modality_pipeline import Modality
from app.services.policy_service import collect_strings, policy_service
from app.services.provider_client import ProviderEndpoint

EMBEDDING_TIMEOUT_SECONDS = 30


async def _embed(request: EmbeddingRequest, api_key: str, endpoint: ProviderEndpoint | None) -> Any:
	# Looked up on the module at call time so the one provider entry point can be replaced in tests.
	return await ls.aembedding(
		**with_endpoint(
			{"model": request.model, "input": request.input, "api_key": api_key, "encoding_format": request.encoding_format, "timeout": EMBEDDING_TIMEOUT_SECONDS},
			api_key, endpoint,
		),
	)


def _usage(body: dict) -> tuple[int, int]:
	usage = body.get("usage", {}) if isinstance(body, dict) else {}
	return int(usage.get("prompt_tokens", usage.get("total_tokens", 0)) or 0), 0


EMBEDDINGS = Modality(
	name="embedding",
	fallback_tag=" (embed)",
	text_of=policy_service.embedding_text,
	estimate_tokens=lambda request: len(policy_service.embedding_text(request)) // 4,
	call=_embed,
	usage=_usage,
	call_type="embedding",
)


# -- rerank ----------------------------------------------------------------------------------------


def _rerank_text(request: RerankRequest) -> str:
	"""Query and every document: all of it goes to the provider, so all of it is scanned and classified."""
	return "\n".join([request.query, *request.texts()])


async def _rerank(request: RerankRequest, api_key: str, endpoint: ProviderEndpoint | None) -> Any:
	kwargs: dict[str, Any] = {
		"model": request.model, "query": request.query, "documents": request.texts(), "return_documents": request.return_documents,
		"api_key": api_key, "timeout": EMBEDDING_TIMEOUT_SECONDS,
	}
	if request.top_n is not None:
		kwargs["top_n"] = request.top_n
	return await ls.arerank(**with_endpoint(kwargs, api_key, endpoint))


def _rerank_usage(body: dict) -> tuple[int, int] | None:
	"""Providers report this differently (``usage``, or Cohere's ``meta.tokens``); none reported means the pipeline estimates."""
	usage = body.get("usage") or {}
	tokens = (body.get("meta") or {}).get("tokens") or {}
	prompt = usage.get("prompt_tokens") or usage.get("total_tokens") or tokens.get("input_tokens")
	return (int(prompt), 0) if prompt else None


RERANK = Modality(
	name="rerank",
	fallback_tag=" (rerank)",
	text_of=_rerank_text,
	estimate_tokens=lambda request: len(_rerank_text(request)) // 4,
	call=_rerank,
	usage=_rerank_usage,
	call_type="rerank",
)


# -- images ----------------------------------------------------------------------------------------

IMAGE_TIMEOUT_SECONDS = 120
IMAGE_RATE_COST_TOKENS = 1_000  # an image is far heavier than its prompt: each one counts as this many tokens against the TPM limit


async def _generate_image(request: ImageRequest, api_key: str, endpoint: ProviderEndpoint | None) -> Any:
	kwargs: dict[str, Any] = {"model": request.model, "prompt": request.prompt, "n": request.n, "api_key": api_key, "timeout": IMAGE_TIMEOUT_SECONDS}
	for field in ("size", "quality", "style", "response_format", "user"):
		value = getattr(request, field)
		if value is not None:
			kwargs[field] = value
	return await ls.aimage_generation(**with_endpoint(kwargs, api_key, endpoint))


IMAGES = Modality(
	name="image",
	fallback_tag=" (image)",
	text_of=lambda request: request.prompt,
	estimate_tokens=lambda request: len(request.prompt) // 4 + request.n * IMAGE_RATE_COST_TOKENS,
	call=_generate_image,
	usage=lambda body: None,  # image generation reports no tokens; the audit row records the prompt's estimated size
	call_type="image_generation",
	units=lambda request: request.n,
)


# -- audio -----------------------------------------------------------------------------------------

AUDIO_TIMEOUT_SECONDS = 300


async def _transcribe(request: TranscriptionRequest, api_key: str, endpoint: ProviderEndpoint | None) -> Any:
	audio = io.BytesIO(request.data)
	audio.name = request.filename  # providers read the format from the name
	kwargs: dict[str, Any] = {"model": request.model, "file": audio, "api_key": api_key, "timeout": AUDIO_TIMEOUT_SECONDS, "response_format": request.response_format}
	for field in ("language", "prompt", "temperature"):
		value = getattr(request, field)
		if value is not None:
			kwargs[field] = value
	return await ls.atranscription(**with_endpoint(kwargs, api_key, endpoint))


def _transcript_text(body: dict) -> str | None:
	text = body.get("text")
	return text if isinstance(text, str) else None


def _with_transcript_text(body: dict, redact) -> dict:
	return {**body, "text": redact(body["text"])}


TRANSCRIPTION = Modality(
	name="transcription",
	fallback_tag=" (transcribe)",
	text_of=lambda request: request.prompt or "",
	estimate_tokens=lambda request: len(request.data) // 4_000 + len(request.prompt or "") // 4,  # about a token per 4 KB of compressed audio
	call=_transcribe,
	usage=lambda body: None,
	opaque_input=lambda request: True,
	call_type="transcription",
	output_text=_transcript_text,
	with_output_text=_with_transcript_text,
)


async def _speak(request: SpeechRequest, api_key: str, endpoint: ProviderEndpoint | None) -> Any:
	kwargs: dict[str, Any] = {"model": request.model, "input": request.input, "voice": request.voice, "response_format": request.response_format, "api_key": api_key, "timeout": AUDIO_TIMEOUT_SECONDS}
	if request.speed is not None:
		kwargs["speed"] = request.speed
	return await ls.aspeech(**with_endpoint(kwargs, api_key, endpoint))


def _render_speech(request_format: str):
	def render(response: Any, headers: dict[str, str]) -> Response:
		content = getattr(response, "content", None)
		if not isinstance(content, (bytes, bytearray)):
			raise RuntimeError("the provider returned no audio")
		return Response(content=bytes(content), media_type=SPEECH_FORMATS[request_format], headers=headers)

	return render


def speech_modality(request: SpeechRequest) -> Modality:
	"""Speech's rendering depends on the format asked for, so the modality is built per request."""
	return Modality(
		name="speech",
		fallback_tag=" (speech)",
		text_of=lambda r: r.input,
		estimate_tokens=lambda r: len(r.input) // 4,
		call=_speak,
		usage=lambda body: None,
		call_type="speech",
		render=_render_speech(request.response_format),
	)


# -- responses -------------------------------------------------------------------------------------

RESPONSES_TIMEOUT_SECONDS = 120
_RESPONSE_FIELDS = ("instructions", "max_output_tokens", "temperature", "top_p", "tools", "tool_choice", "parallel_tool_calls", "text", "metadata", "user", "truncation")


def _responses_text(request: ResponsesRequest) -> str:
    """Everything the model will read: input (including tool definitions and structured parts), instructions and output format."""
    parts: list[str] = []
    collect_strings(
        [request.input, request.instructions, request.tools, request.tool_choice, request.text, request.metadata], parts
    )
    return "\n".join(parts)


def _responses_check(request: ResponsesRequest, policy: Any) -> None:
    if (request.store or request.previous_response_id) and not policy.allow_provider_response_state:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail={
                "error": "provider_state_not_allowed",
                "detail": "store=true and previous_response_id keep conversation state at the provider, which this organization has not allowed. "
                "Send the full input each time with store=false.",
            },
        )


async def _respond(request: ResponsesRequest, api_key: str, endpoint: ProviderEndpoint | None) -> Any:
    # ``store`` is always sent explicitly: the provider's default is to keep the response, which would put prompts where the org's rules do not reach.
    kwargs: dict[str, Any] = {"model": request.model, "input": request.input, "store": bool(request.store), "api_key": api_key, "timeout": RESPONSES_TIMEOUT_SECONDS}
    for field in _RESPONSE_FIELDS:
        value = getattr(request, field)
        if value is not None:
            kwargs[field] = value
    if request.previous_response_id:
        kwargs["previous_response_id"] = request.previous_response_id
    return await ls.aresponses(**with_endpoint(kwargs, api_key, endpoint))


def _output_text_parts(body: dict):
    for item in body.get("output") or []:
        for part in (item.get("content") or []) if isinstance(item, dict) else []:
            if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                yield part


def _response_text(body: dict) -> str | None:
    texts = [part["text"] for part in _output_text_parts(body)]
    return "\n".join(texts) if texts else None


def _with_response_text(body: dict, redact) -> dict:
    """Every text part of the answer, redacted on its own with the org's redactor."""
    out = {**body, "output": [dict(item) if isinstance(item, dict) else item for item in body.get("output") or []]}
    for item in out["output"]:
        if isinstance(item, dict) and isinstance(item.get("content"), list):
            item["content"] = [
                {**part, "text": redact(part["text"])} if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str) else part
                for part in item["content"]
            ]
    return out


def _responses_usage(body: dict) -> tuple[int, int] | None:
    usage = body.get("usage") or {}
    if "input_tokens" not in usage and "output_tokens" not in usage:
        return None
    return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)


RESPONSES = Modality(
    name="responses",
    fallback_tag=" (responses)",
    text_of=_responses_text,
    estimate_tokens=lambda request: len(_responses_text(request)) // 4,
    call=_respond,
    usage=_responses_usage,
    opaque_input=lambda request: request.has_uninspectable_input(),
    check=_responses_check,
    call_type="responses",
    output_text=_response_text,
    with_output_text=_with_response_text,
)
