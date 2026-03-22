"""Eval hook (HTTP / LLM-as-judge) tests — fail-open, score parsing, storage."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.eval_service import (
	_extract_prompt_text,
	_parse_scores_from_hook_response,
	_parse_score_from_llm_response,
	run_eval_hook,
)


def test_extract_prompt_text_from_messages():
	"""Message objects with content extracted."""
	class Msg:
		def __init__(self, content):
			self.content = content
	msgs = [Msg("Hello"), Msg("World")]
	assert _extract_prompt_text(msgs) == "Hello\nWorld"


def test_extract_prompt_text_from_dicts():
	"""Dict messages with content key."""
	assert _extract_prompt_text([{"content": "Hi"}]) == "Hi"


def test_parse_scores_from_hook_scores_format():
	"""Hook returns {scores: [{name, value}]}."""
	assert _parse_scores_from_hook_response({"scores": [{"name": "quality", "value": 4.5}]}) == [("quality", 4.5)]
	assert _parse_scores_from_hook_response({"scores": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]}) == [("a", 1.0), ("b", 2.0)]


def test_parse_scores_from_hook_single_score():
	"""Hook returns {score: n}."""
	assert _parse_scores_from_hook_response({"score": 4}) == [("quality", 4.0)]
	assert _parse_scores_from_hook_response({"score": 3.5}) == [("quality", 3.5)]


def test_parse_scores_from_hook_empty():
	"""Missing/invalid keys return empty."""
	assert _parse_scores_from_hook_response({}) == []
	assert _parse_scores_from_hook_response({"other": 1}) == []


def test_parse_score_from_llm_response():
	"""Extract number from LLM text."""
	assert _parse_score_from_llm_response("4") == 4.0
	assert _parse_score_from_llm_response("4.5") == 4.5
	assert _parse_score_from_llm_response("The score is 3.7") == 3.7
	assert _parse_score_from_llm_response("") is None
	assert _parse_score_from_llm_response("no numbers") is None


@pytest.mark.asyncio
async def test_run_eval_hook_no_config(monkeypatch):
	"""When neither EVAL_HOOK_URL nor EVAL_LLM_MODEL set, no-op."""
	monkeypatch.setattr("app.services.eval_service.settings", SimpleNamespace(EVAL_HOOK_URL="", EVAL_LLM_MODEL=""))
	await run_eval_hook(uuid4(), uuid4(), None, None, "prompt", "response")
	# No exception, no external calls


@pytest.mark.asyncio
async def test_run_eval_hook_http_called_when_url_set(monkeypatch):
	"""When EVAL_HOOK_URL set, HTTP POST is made with prompt/response."""
	req_id = uuid4()
	org_id = uuid4()
	exp_id = uuid4()
	var_id = uuid4()
	monkeypatch.setattr("app.services.eval_service.settings", SimpleNamespace(EVAL_HOOK_URL="https://eval.example/score", EVAL_LLM_MODEL=""))

	post_calls = []

	async def fake_post(*args, **kwargs):
		post_calls.append(kwargs)
		r = MagicMock()
		r.status_code = 200
		r.raise_for_status = MagicMock()
		r.json = lambda: {"scores": [{"name": "quality", "value": 4.5}]}
		return r

	with patch("app.services.eval_service.httpx.AsyncClient") as mock_client:
		ctx = MagicMock()
		ctx.post = AsyncMock(side_effect=fake_post)
		ctx.__aenter__ = AsyncMock(return_value=ctx)
		ctx.__aexit__ = AsyncMock(return_value=None)
		mock_client.return_value = ctx

		with patch("app.services.eval_service.AsyncSessionLocal") as mock_session:
			sess = MagicMock()
			sess.execute = AsyncMock()
			sess.commit = AsyncMock()
			sess.__aenter__ = AsyncMock(return_value=sess)
			sess.__aexit__ = AsyncMock(return_value=None)
			mock_session.return_value = sess
			with patch("app.services.eval_service.set_session_org_id", AsyncMock()):
				await run_eval_hook(req_id, org_id, exp_id, var_id, "prompt", "response")

	assert len(post_calls) == 1
	assert post_calls[0]["json"]["prompt"] == "prompt"
	assert post_calls[0]["json"]["response"] == "response"
	assert post_calls[0]["json"]["request_id"] == str(req_id)
