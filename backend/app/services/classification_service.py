"""Data classification: how sensitive is this request?

The effective class is the highest of three things:

* the org's default class (``PolicyConfig.default_data_class``),
* the class the caller asserts in ``X-OpenProxy-Data-Class`` (it can only raise the class, never lower it),
* the class of each kind of PII found in the text, through the org's ``data_class_map`` over built-in defaults.

Classification only describes a request. Nothing here blocks or routes: that is the router's job (Phase 2, S4).
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from app.schemas.chat import ChatCompletionRequest, EmbeddingRequest
from app.services import presidio_service
from app.services.data_class import DATA_CLASSES, DataClass, data_class_rank
from app.services.policy_service import PolicyConfig, PolicyScanLimitExceeded, policy_service

DATA_CLASS_HEADER: Final = "x-openproxy-data-class"

# Standing in for "we could not inspect this text" (an oversized request). Not assumed harmless.
UNSCANNED: Final = "__unscanned__"

DEFAULT_CLASS_MAP: Final[dict[str, DataClass]] = {
	# Regex detector names
	"ssn": "confidential",
	"payment_card": "confidential",
	"email": "internal",
	# Presidio entity types
	"US_SSN": "confidential",
	"US_ITIN": "confidential",
	"US_PASSPORT": "confidential",
	"US_DRIVER_LICENSE": "confidential",
	"US_BANK_NUMBER": "confidential",
	"CREDIT_CARD": "confidential",
	"IBAN_CODE": "confidential",
	"CRYPTO": "confidential",
	"MEDICAL_LICENSE": "confidential",
	"UK_NHS": "confidential",
	"EMAIL_ADDRESS": "internal",
	"PHONE_NUMBER": "internal",
	"PERSON": "internal",
	"LOCATION": "internal",
	"IP_ADDRESS": "internal",
	UNSCANNED: "confidential",
}

_PRIORITY = {"default": 0, "header": 1, "detected": 2}  # on a tie, the most specific reason is reported


class InvalidDataClass(ValueError):
	"""The caller asserted a data class we do not know. Fail loudly: a typo must not silently mean "no claim"."""


@dataclass(frozen=True)
class Classification:
	data_class: DataClass
	source: str  # "default", "header" or "detected": what set the class
	entities: tuple[str, ...]  # kinds of PII found (names only, never the text)

	def as_metadata(self) -> dict:
		return {"class": self.data_class, "source": self.source, "entities": list(self.entities)}


def effective_class_map(config: PolicyConfig) -> dict[str, str]:
	return {**DEFAULT_CLASS_MAP, **config.data_class_map}


def _parse_header(value: str) -> DataClass:
	cleaned = value.strip().lower()
	if cleaned not in DATA_CLASSES:
		raise InvalidDataClass(f"Unknown data class {value!r}. Use one of: {', '.join(DATA_CLASSES)}.")
	return cleaned  # type: ignore[return-value]


def classify(
	*,
	default_class: str,
	header_value: str | None,
	entities: Sequence[str],
	class_map: Mapping[str, str],
) -> Classification:
	"""Pure rule: the highest class among the default, the header and every mapped entity."""
	candidates: list[tuple[int, int, str]] = [(data_class_rank(default_class), _PRIORITY["default"], default_class)]
	if header_value is not None:
		asserted = _parse_header(header_value)
		candidates.append((data_class_rank(asserted), _PRIORITY["header"], asserted))
	for entity in entities:
		mapped = class_map.get(entity)
		if mapped is not None:
			candidates.append((data_class_rank(mapped), _PRIORITY["detected"], mapped))
	rank, priority, chosen = max(candidates, key=lambda c: (c[0], c[1]))
	source = next(name for name, value in _PRIORITY.items() if value == priority)
	return Classification(chosen, source, tuple(entities))  # type: ignore[arg-type]


async def detect_entities(text: str, config: PolicyConfig) -> list[str]:
	"""Kinds of PII in the text. Presidio's NLP pass runs in a worker thread so it cannot stall the event loop."""
	if presidio_service.is_enabled():
		return await asyncio.to_thread(policy_service.pii_entities_found, text, config)
	return policy_service.pii_entities_found(text, config)


async def classify_text(text: str | None, config: PolicyConfig, header_value: str | None) -> Classification:
	"""Classify extracted text; ``None`` means it could not be scanned."""
	entities = [UNSCANNED] if text is None else await detect_entities(text, config)
	return classify(
		default_class=config.default_data_class,
		header_value=header_value,
		entities=entities,
		class_map=effective_class_map(config),
	)


async def classify_chat_request(request: ChatCompletionRequest, config: PolicyConfig, header_value: str | None) -> Classification:
	try:
		text: str | None = policy_service.chat_text(request)
	except PolicyScanLimitExceeded:
		text = None
	return await classify_text(text, config, header_value)


async def classify_embedding_request(request: EmbeddingRequest, config: PolicyConfig, header_value: str | None) -> Classification:
	return await classify_text(policy_service.embedding_text(request), config, header_value)
