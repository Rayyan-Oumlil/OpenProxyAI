"""Opt-in capture of redacted prompts and answers for evaluation (Phase 3, slice 2).

Stored text is the one place this product keeps what users typed, so every rule here errs toward storing less:

- Off unless the org sets a sample rate above 0 (``PolicyConfig.payload_capture_sample_rate``).
- Never above ``PAYLOAD_CAPTURE_MAX_DATA_CLASS`` (default ``internal``), whatever the rate.
- PII is replaced with the same detector the policy uses *before* anything is written; the row records that it was.
- Only role and content are kept. Tool calls and other extras are dropped, and non-text parts become a marker.
- Rows expire with the plan's audit retention and a daily job deletes them.
- Capturing runs in the background and can never change an HTTP result: every failure is logged and swallowed.
"""

from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.config import PLAN_FEATURES
from app.database import AsyncSessionLocal, org_scoped_session, set_session_org_id
from app.models.organization import Organization
from app.models.request_payload import RequestPayload
from app.services import pii_detection
from app.services.data_class import data_class_rank

logger = logging.getLogger(__name__)

MAX_FIELD_CHARS: Final = 50_000
TRUNCATION_MARK: Final = "\n[truncated]"


def should_capture(*, sample_rate: Any, data_class: str, ceiling: str, draw: float | None = None) -> bool:
	"""True when this request is to be kept. ``draw`` is a number in [0, 1): the request is kept if it is below the rate."""
	if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, float)):
		return False
	if not math.isfinite(sample_rate) or not 0 < sample_rate <= 1:
		return False
	try:
		if data_class_rank(data_class) > data_class_rank(ceiling):
			return False
	except ValueError:
		return False  # an unknown class is never guessed at
	return (random.random() if draw is None else draw) < sample_rate


def _cut(text: str) -> str:
	return text if len(text) <= MAX_FIELD_CHARS else text[:MAX_FIELD_CHARS] + TRUNCATION_MARK


def _clean_text(text: str) -> tuple[str, bool]:
	# Redact first and cut after: cutting first could split a value at the boundary and leave half of it undetected.
	cleaned = pii_detection.redact(text)
	return _cut(cleaned), cleaned != text


def prepare_output(text: str) -> tuple[str, bool]:
	"""The answer, cut to size and stripped of PII, and whether anything was replaced."""
	return _clean_text(text or "")


def _clean_content(content: Any) -> tuple[Any, bool]:
	if content is None:
		return None, False
	if isinstance(content, str):
		return _clean_text(content)
	if isinstance(content, list):
		parts, any_redacted = [], False
		for part in content:
			if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
				text, changed = _clean_text(part["text"])
				parts.append({"type": "text", "text": text})
				any_redacted = any_redacted or changed
			else:
				kind = part.get("type") if isinstance(part, dict) else None
				parts.append({"type": "omitted", "was": kind if isinstance(kind, str) else "unknown"})
		return parts, any_redacted
	return None, False


def prepare_messages(messages: Any) -> tuple[list[dict], bool]:
	"""Role and content of each message, text redacted, nothing else, and whether anything was replaced."""
	stored, any_redacted = [], False
	for message in messages or []:
		data = message.model_dump() if hasattr(message, "model_dump") else dict(message)
		content, changed = _clean_content(data.get("content"))
		stored.append({"role": data.get("role"), "content": content})
		any_redacted = any_redacted or changed
	return stored, any_redacted


async def capture_payload(org_id: uuid.UUID, request_id: uuid.UUID, messages: Any, output: str, *, now: datetime | None = None) -> bool:
	"""Redact, then store one request's prompt and answer. Never raises; returns whether a row was written."""
	try:
		stored_messages, messages_redacted = prepare_messages(messages)
		stored_output, output_redacted = prepare_output(output)
		moment = now or datetime.now(UTC)
		async with org_scoped_session(org_id) as db:
			org = await db.get(Organization, org_id)
			plan = (getattr(org, "plan", None) or "community").lower()
			retention_days = PLAN_FEATURES.get(plan, PLAN_FEATURES["community"])["audit_retention_days"]
			fields = {
				"messages": stored_messages,
				"output": stored_output,
				"redacted": messages_redacted or output_redacted,
				"expires_at": moment + timedelta(days=retention_days),
			}
			await db.execute(
				insert(RequestPayload)
				.values(org_id=org_id, request_id=request_id, **fields)
				.on_conflict_do_update(index_elements=["org_id", "request_id"], set_=fields)
			)
			await db.commit()
		return True
	except Exception:
		logger.exception("payload capture failed for request %s", request_id)
		return False


async def purge_expired_payloads(now: datetime | None = None) -> int:
	"""Delete rows past their expiry, one organization at a time (row-level security is forced). Returns how many."""
	moment = now or datetime.now(UTC)
	deleted = 0
	try:
		async with AsyncSessionLocal() as session:
			for org_id in list(await session.scalars(select(Organization.id))):
				await set_session_org_id(session, org_id)
				result = await session.execute(
					delete(RequestPayload).where(RequestPayload.org_id == org_id, RequestPayload.expires_at < moment)
				)
				deleted += result.rowcount or 0
			await session.commit()
		logger.info("purge_expired_payloads removed %d rows", deleted)
	except Exception:
		logger.exception("Failed to purge expired payloads")
	return deleted
