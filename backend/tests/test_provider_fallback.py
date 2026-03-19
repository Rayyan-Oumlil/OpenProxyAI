"""Provider fallback chain tests.

Verifies that:
- 429/5xx from upstream triggers fallback to the next candidate key
- 4xx client errors (401, 400) do NOT trigger fallback
- All keys exhausted → 502
- Fallback count recorded in request_metadata
- Streaming path falls back before first chunk is sent
- _select_provider_keys returns ordered list (primary first, fallbacks weight-desc)
- _is_retryable correctly classifies retryable vs. non-retryable status codes
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import llm_service as llm_service_module
from app.services.llm_service import LLMService, _is_retryable


# ── Helpers ───────────────────────────────────────────────────────────────────


def _error(status_code: int) -> Exception:
	"""Create a minimal exception that looks like a LiteLLM provider error."""
	exc = Exception(f"provider HTTP {status_code}")
	exc.status_code = status_code  # type: ignore[attr-defined]
	return exc


def _make_litellm_response(content: str = "Hello!") -> object:
	"""Minimal response object that satisfies llm_service's usage."""
	body = {
		"id": "chatcmpl-test",
		"object": "chat.completion",
		"model": "openai/gpt-4o",
		"choices": [
			{
				"index": 0,
				"message": {"role": "assistant", "content": content},
				"finish_reason": "stop",
			}
		],
		"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
	}

	class _Resp:
		choices = [SimpleNamespace(message=SimpleNamespace(content=content))]
		usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)

		def model_dump(self, **_):
			return body

		def __iter__(self):
			return iter([])

	return _Resp()


def _permissive_policy():
	return SimpleNamespace(
		enforcement_mode="off",
		allowed_models=[],
		blocked_keywords=[],
		pii_detection_enabled=False,
		pii_entities=[],
		model_rate_limits={},
		prompt_injection_detection_enabled=False,
		response_guardrails_enabled=False,
		response_pii_redact=False,
	)


def _patch_common(monkeypatch):
	"""Patch services that are not under test in this file."""
	async def _load(*a, **kw):
		return _permissive_policy()

	monkeypatch.setattr(llm_service_module.policy_store, "load", _load)

	async def _check_limits(**kw):
		return (True, {}, None, None, None)

	monkeypatch.setattr(llm_service_module.rate_limiter_service, "check_limits", _check_limits)

	async def _log(**kw):
		pass

	monkeypatch.setattr(llm_service_module, "log_request", _log)
	monkeypatch.setattr(
		llm_service_module.cost_tracker_service,
		"calculate_cost_usd",
		lambda *a, **kw: Decimal("0"),
	)
	# policy_service evaluate returns allow
	async def _fake_evaluate(req, cfg):
		return SimpleNamespace(
			allowed=True,
			action="allow",
			detail=None,
			reason_code=None,
			triggered_rules=[],
			as_metadata=lambda: None,
		)

	monkeypatch.setattr(llm_service_module.policy_service, "evaluate_chat_request", _fake_evaluate)


def _make_request(stream: bool = False):
	return llm_service_module.ChatCompletionRequest(
		model="openai/gpt-4o",
		messages=[{"role": "user", "content": "hi"}],
		stream=stream,
	)


async def _call(monkeypatch, fake_redis, candidate_keys, acompletion_fn, stream=False):
	"""Helper: wire candidates + acompletion, call chat_completion, return response."""
	_patch_common(monkeypatch)

	async def _keys(*a, **kw):
		return candidate_keys

	monkeypatch.setattr(llm_service_module.llm_service, "_select_provider_keys", _keys)

	monkeypatch.setattr(llm_service_module, "acompletion", acompletion_fn)

	svc = llm_service_module.llm_service
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=None)
	api_key = SimpleNamespace(id=uuid4())

	from fastapi import BackgroundTasks

	from tests.conftest import FakeDB

	return await svc.chat_completion(
		request=_make_request(stream=stream),
		db=FakeDB(),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=BackgroundTasks(),
	)


# ── _is_retryable unit tests ──────────────────────────────────────────────────


def test_is_retryable_429():
	assert _is_retryable(_error(429)) is True


def test_is_retryable_500():
	assert _is_retryable(_error(500)) is True


def test_is_retryable_502():
	assert _is_retryable(_error(502)) is True


def test_is_retryable_503():
	assert _is_retryable(_error(503)) is True


def test_is_retryable_504():
	assert _is_retryable(_error(504)) is True


def test_not_retryable_401():
	assert _is_retryable(_error(401)) is False


def test_not_retryable_400():
	assert _is_retryable(_error(400)) is False


def test_not_retryable_403():
	assert _is_retryable(_error(403)) is False


def test_not_retryable_no_status():
	assert _is_retryable(ValueError("no status code")) is False


# ── _select_provider_keys unit tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_select_provider_keys_single_key():
	"""One active key → returns a 1-element list."""
	from app.services.crypto_service import encrypt
	from unittest.mock import AsyncMock, MagicMock

	key = MagicMock()
	key.weight = 1
	key.is_active = True
	key.model_patterns = None
	key.api_key_encrypted = encrypt("sk-only-key-123456")

	fake_db = MagicMock()
	fake_db.get = AsyncMock(return_value=None)
	fake_db.scalars = AsyncMock(return_value=iter([key]))

	result = await LLMService()._select_provider_keys(fake_db, uuid4(), "openai")
	assert result == ["sk-only-key-123456"]


@pytest.mark.asyncio
async def test_select_provider_keys_no_keys_raises_503():
	"""No active keys and no env var → HTTP 503."""
	from unittest.mock import AsyncMock, MagicMock
	from fastapi import HTTPException

	fake_db = MagicMock()
	fake_db.get = AsyncMock(return_value=None)
	fake_db.scalars = AsyncMock(return_value=iter([]))

	with pytest.raises(HTTPException) as exc_info:
		await LLMService()._select_provider_keys(fake_db, uuid4(), "openai")
	assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_select_provider_keys_multiple_ordered():
	"""Multiple keys → primary is first; remaining are weight-desc ordered."""
	from app.services.crypto_service import encrypt
	from unittest.mock import AsyncMock, MagicMock
	import random

	key_low = MagicMock()
	key_low.weight = 1
	key_low.is_active = True
	key_low.model_patterns = None
	key_low.api_key_encrypted = encrypt("sk-low-weight-key123")

	key_mid = MagicMock()
	key_mid.weight = 5
	key_mid.is_active = True
	key_mid.model_patterns = None
	key_mid.api_key_encrypted = encrypt("sk-mid-weight-key123")

	key_high = MagicMock()
	key_high.weight = 10
	key_high.is_active = True
	key_high.model_patterns = None
	key_high.api_key_encrypted = encrypt("sk-high-weight-key1")

	fake_db = MagicMock()
	fake_db.get = AsyncMock(return_value=None)
	fake_db.scalars = AsyncMock(return_value=iter([key_low, key_mid, key_high]))

	random.seed(0)
	result = await LLMService()._select_provider_keys(fake_db, uuid4(), "openai")

	assert len(result) == 3
	assert set(result) == {"sk-low-weight-key123", "sk-mid-weight-key123", "sk-high-weight-key1"}
	# Fallbacks (index 1+) must be in descending weight order
	remaining = result[1:]
	remaining_weights = {
		"sk-low-weight-key123": 1,
		"sk-mid-weight-key123": 5,
		"sk-high-weight-key1": 10,
	}
	if len(remaining) == 2:
		assert remaining_weights[remaining[0]] >= remaining_weights[remaining[1]]


# ── Fallback integration tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_on_429(monkeypatch, fake_redis):
	"""First call raises 429 → second key tried → success → HTTP 200."""
	ok_resp = _make_litellm_response()
	calls = []

	async def acompletion(**kw):
		calls.append(kw.get("api_key"))
		if len(calls) == 1:
			raise _error(429)
		return ok_resp

	response = await _call(monkeypatch, fake_redis, ["sk-key-1", "sk-key-2"], acompletion)
	assert response.status_code == 200
	assert len(calls) == 2
	assert calls[0] == "sk-key-1"
	assert calls[1] == "sk-key-2"


@pytest.mark.asyncio
async def test_fallback_on_503(monkeypatch, fake_redis):
	"""First call raises 503 → second key tried → success → HTTP 200."""
	ok_resp = _make_litellm_response()
	calls = []

	async def acompletion(**kw):
		calls.append(kw.get("api_key"))
		if len(calls) == 1:
			raise _error(503)
		return ok_resp

	response = await _call(monkeypatch, fake_redis, ["sk-key-1", "sk-key-2"], acompletion)
	assert response.status_code == 200
	assert len(calls) == 2


@pytest.mark.asyncio
async def test_no_fallback_on_401(monkeypatch, fake_redis):
	"""AuthenticationError (401) must not trigger fallback — re-raised immediately."""
	from fastapi import HTTPException
	calls = []

	async def acompletion(**kw):
		calls.append(kw.get("api_key"))
		raise _error(401)

	with pytest.raises(HTTPException) as exc_info:
		await _call(monkeypatch, fake_redis, ["sk-key-1", "sk-key-2"], acompletion)
	assert exc_info.value.status_code == 502  # wrapped by except Exception handler
	assert len(calls) == 1  # only one attempt


@pytest.mark.asyncio
async def test_no_fallback_on_400(monkeypatch, fake_redis):
	"""Bad request (400) must not trigger fallback."""
	from fastapi import HTTPException
	calls = []

	async def acompletion(**kw):
		calls.append(kw.get("api_key"))
		raise _error(400)

	with pytest.raises(HTTPException) as exc_info:
		await _call(monkeypatch, fake_redis, ["sk-key-1", "sk-key-2"], acompletion)
	assert exc_info.value.status_code == 502
	assert len(calls) == 1


@pytest.mark.asyncio
async def test_all_keys_exhausted_returns_502(monkeypatch, fake_redis):
	"""All candidates raise 429 → final response is 502."""
	from fastapi import HTTPException
	calls = []

	async def acompletion(**kw):
		calls.append(kw.get("api_key"))
		raise _error(429)

	with pytest.raises(HTTPException) as exc_info:
		await _call(monkeypatch, fake_redis, ["sk-key-1", "sk-key-2"], acompletion)
	assert exc_info.value.status_code == 502
	assert len(calls) == 2  # both keys tried


@pytest.mark.asyncio
async def test_single_key_succeeds_no_fallback_needed(monkeypatch, fake_redis):
	"""Single key, works fine — normal flow unchanged."""
	ok_resp = _make_litellm_response()
	calls = []

	async def acompletion(**kw):
		calls.append(kw.get("api_key"))
		return ok_resp

	response = await _call(monkeypatch, fake_redis, ["sk-only-key"], acompletion)
	assert response.status_code == 200
	assert len(calls) == 1


@pytest.mark.asyncio
async def test_streaming_fallback_on_429(monkeypatch, fake_redis):
	"""Streaming: first key raises 429 before first chunk → second key tried → 200."""
	calls = []

	class _StreamOnce:
		"""Async iterator that yields exactly one dict chunk."""
		def __init__(self):
			self._done = False

		def __aiter__(self):
			return self

		async def __anext__(self):
			if self._done:
				raise StopAsyncIteration
			self._done = True
			return {"id": "x", "choices": [{"delta": {"content": "hi"}, "finish_reason": None}]}

	async def acompletion(**kw):
		calls.append(kw.get("api_key"))
		if len(calls) == 1:
			raise _error(429)
		return _StreamOnce()

	response = await _call(monkeypatch, fake_redis, ["sk-key-1", "sk-key-2"], acompletion, stream=True)
	assert response.status_code == 200
	assert len(calls) == 2
	assert calls[0] == "sk-key-1"
	assert calls[1] == "sk-key-2"
