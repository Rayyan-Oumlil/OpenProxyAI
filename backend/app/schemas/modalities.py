"""Request schemas for the non-chat endpoints (Phase 5). Limits are here because everything in a request is scanned by policy."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_MODEL_CHARS = 100
Model = Annotated[str, StringConstraints(min_length=1, max_length=MAX_MODEL_CHARS)]

MAX_RERANK_DOCUMENTS = 1_000
MAX_RERANK_QUERY_CHARS = 10_000
MAX_RERANK_DOCUMENT_CHARS = 50_000
MAX_RERANK_TOTAL_CHARS = 1_000_000


class RerankRequest(BaseModel):
	"""Cohere-style rerank: ``documents`` are strings (or ``{"text": ...}`` objects), returned ordered by relevance to ``query``."""

	model_config = ConfigDict(extra="forbid")

	model: Model
	query: str = Field(min_length=1, max_length=MAX_RERANK_QUERY_CHARS)
	documents: list[str | dict[str, str]] = Field(min_length=1, max_length=MAX_RERANK_DOCUMENTS)
	top_n: int | None = Field(default=None, ge=1, le=MAX_RERANK_DOCUMENTS)
	return_documents: bool = True

	@field_validator("documents")
	@classmethod
	def _sized(cls, documents: list[str | dict[str, str]]) -> list[str | dict[str, str]]:
		total = 0
		for document in documents:
			text = document if isinstance(document, str) else document.get("text")
			if not isinstance(text, str):
				raise ValueError('a document is a string or {"text": "..."}')
			if len(text) > MAX_RERANK_DOCUMENT_CHARS:
				raise ValueError(f"a document is longer than {MAX_RERANK_DOCUMENT_CHARS} characters")
			total += len(text)
		if total > MAX_RERANK_TOTAL_CHARS:
			raise ValueError(f"the documents together are longer than {MAX_RERANK_TOTAL_CHARS} characters")
		return documents

	def texts(self) -> list[str]:
		return [d if isinstance(d, str) else d["text"] for d in self.documents]


MAX_IMAGE_PROMPT_CHARS = 4_000
MAX_IMAGES_PER_REQUEST = 4
ImageSize = Literal["auto", "256x256", "512x512", "1024x1024", "1024x1536", "1536x1024", "1024x1792", "1792x1024"]


class ImageRequest(BaseModel):
	"""OpenAI-style image generation. The prompt is the only text, and it is scanned like any prompt."""

	model_config = ConfigDict(extra="forbid")

	model: Model
	prompt: str = Field(min_length=1, max_length=MAX_IMAGE_PROMPT_CHARS)
	n: int = Field(default=1, ge=1, le=MAX_IMAGES_PER_REQUEST)
	size: ImageSize | None = None
	quality: Literal["standard", "hd", "low", "medium", "high", "auto"] | None = None
	style: Literal["vivid", "natural"] | None = None
	response_format: Literal["url", "b64_json"] | None = None
	user: str | None = Field(default=None, max_length=200)
