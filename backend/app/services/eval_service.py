"""Experiment eval hook — HTTP callback or LLM-as-judge to auto-submit quality scores."""

import logging
import re
from uuid import UUID

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.database import AsyncSessionLocal, set_session_org_id
from app.models.request_score import RequestScore

logger = logging.getLogger(__name__)


def _extract_prompt_text(messages: list) -> str:
	"""Concatenate user-facing content from messages for eval."""
	parts: list[str] = []
	for msg in messages:
		content = getattr(msg, "content", None) if hasattr(msg, "content") else (msg.get("content") if isinstance(msg, dict) else None)
		if content is None:
			continue
		if isinstance(content, str):
			parts.append(content)
			continue
		if isinstance(content, list):
			for item in content:
				if isinstance(item, str):
					parts.append(item)
				elif isinstance(item, dict) and isinstance(item.get("text"), str):
					parts.append(item["text"])
	return "\n".join(parts)


def _parse_scores_from_hook_response(data: dict) -> list[tuple[str, float]]:
	"""Parse hook response: {scores: [{name, value}]} or {score: n}."""
	scores: list[tuple[str, float]] = []
	if "scores" in data and isinstance(data["scores"], list):
		for s in data["scores"]:
			if isinstance(s, dict):
				name = s.get("name")
				val = s.get("value")
				if name and isinstance(val, (int, float)):
					scores.append((str(name), float(val)))
	elif "score" in data:
		v = data["score"]
		if isinstance(v, (int, float)):
			scores.append(("quality", float(v)))
	return scores


def _parse_score_from_llm_response(text: str) -> float | None:
	"""Extract numeric score from LLM judge response (e.g. '4' or '4.5')."""
	if not text or not isinstance(text, str):
		return None
	text = text.strip()
	match = re.search(r"(\d+(?:\.\d+)?)", text)
	return float(match.group(1)) if match else None


async def _call_http_hook(prompt_text: str, response_text: str, request_id: UUID) -> list[tuple[str, float]]:
	"""POST to EVAL_HOOK_URL; parse scores from JSON response. Fail-open."""
	url = settings.EVAL_HOOK_URL.strip()
	if not url:
		return []
	try:
		async with httpx.AsyncClient(timeout=30.0) as client:
			r = await client.post(
				url,
				json={
					"prompt": prompt_text,
					"response": response_text,
					"request_id": str(request_id),
				},
				headers={"Content-Type": "application/json"},
			)
			r.raise_for_status()
			data = r.json()
			return _parse_scores_from_hook_response(data)
	except Exception as exc:
		logger.warning("Eval hook failed (request_id=%s): %s", request_id, exc)
		return []


async def _call_llm_judge(prompt_text: str, response_text: str) -> list[tuple[str, float]]:
	"""Call LLM with judge prompt; parse score. Fail-open."""
	model = settings.EVAL_LLM_MODEL.strip()
	if not model:
		return []
	try:
		from litellm import acompletion

		judge_prompt = (
			f"Rate the following LLM response on quality from 1 (poor) to 5 (excellent). "
			f"Reply with only a single number.\n\nPrompt:\n{prompt_text[:2000]}\n\nResponse:\n{response_text[:2000]}"
		)
		resp = await acompletion(
			model=model,
			messages=[{"role": "user", "content": judge_prompt}],
			timeout=15,
		)
		content = ""
		if resp and resp.choices:
			content = (resp.choices[0].message.content or "").strip()
		score = _parse_score_from_llm_response(content)
		if score is not None:
			return [("quality", score)]
		logger.warning("LLM judge returned unparseable content: %r", content[:200])
		return []
	except Exception as exc:
		logger.warning("LLM-as-judge failed: %s", exc)
		return []


async def run_eval_hook(
	request_id: UUID,
	org_id: UUID,
	experiment_id: UUID | None,
	variant_id: UUID | None,
	prompt_text: str,
	response_text: str,
) -> None:
	"""Run eval hook (HTTP or LLM); store scores. Fail-open — never raises."""
	if not settings.EVAL_HOOK_URL.strip() and not settings.EVAL_LLM_MODEL.strip():
		return

	scores: list[tuple[str, float]] = []
	if settings.EVAL_HOOK_URL.strip():
		scores = await _call_http_hook(prompt_text, response_text, request_id)
	if not scores and settings.EVAL_LLM_MODEL.strip():
		scores = await _call_llm_judge(prompt_text, response_text)

	if not scores:
		return

	try:
		async with AsyncSessionLocal() as db:
			await set_session_org_id(db, org_id)
			for name, value in scores:
				stmt = insert(RequestScore).values(
					request_id=request_id,
					org_id=org_id,
					experiment_id=experiment_id,
					variant_id=variant_id,
					score_name=name,
					value=value,
				).on_conflict_do_update(
					index_elements=["request_id", "score_name"],
					set_={
						RequestScore.value: value,
						RequestScore.experiment_id: experiment_id,
						RequestScore.variant_id: variant_id,
					},
				)
				await db.execute(stmt)
			await db.commit()
	except Exception as exc:
		logger.warning("Failed to store eval scores (request_id=%s): %s", request_id, exc)
