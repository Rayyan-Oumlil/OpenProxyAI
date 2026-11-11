"""The endpoint-specific parts of each non-chat modality (Phase 5). The sequence they all run through is in ``modality_pipeline``."""

from __future__ import annotations

from typing import Any

from app.schemas.chat import EmbeddingRequest
from app.schemas.modalities import RerankRequest
from app.services import llm_service as ls
from app.services.llm_service import with_endpoint
from app.services.modality_pipeline import Modality
from app.services.policy_service import policy_service
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
)
