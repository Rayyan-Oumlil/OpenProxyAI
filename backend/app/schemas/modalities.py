"""Request schemas for the non-chat endpoints (Phase 5). Limits are here because everything in a request is scanned by policy."""

from __future__ import annotations

from typing import Annotated

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
