"""The endpoint-specific parts of each non-chat modality (Phase 5). The sequence they all run through is in ``modality_pipeline``."""

from __future__ import annotations

from typing import Any

from app.schemas.chat import EmbeddingRequest
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
