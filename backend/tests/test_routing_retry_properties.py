"""The retry path under random upstream failures (Phase 2): a retry may only ever reach a key the router chose.

``test_routing_core`` proves the authorized set is computed correctly. This file covers the other half the blog post
admits was untested: once a request is routed, every attempt the gateway makes while an upstream is failing stays inside
the candidate keys it was handed (under enforce, the registry key and, for a fallback model, that model's own key).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.llm_service import _RETRYABLE_STATUS_CODES, LLMService, _is_retryable

SETTINGS = settings(max_examples=300, deadline=None)

NON_RETRYABLE = (400, 401, 403, 404, 422)
RETRYABLE = tuple(sorted(_RETRYABLE_STATUS_CODES))


def provider_error(status_code: int) -> Exception:
	exc = Exception(f"provider HTTP {status_code}")
	exc.status_code = status_code  # type: ignore[attr-defined]
	return exc


# Each step of a script is what one upstream call does: succeed, fail with a status, or raise a gateway HTTPException.
steps = st.one_of(
	st.just(("ok", None)),
	st.sampled_from(RETRYABLE).map(lambda code: ("fail", code)),
	st.sampled_from(NON_RETRYABLE).map(lambda code: ("fail", code)),
	st.just(("http", 451)),
)
scripts = st.lists(steps, min_size=1, max_size=8)


def run(coroutine):
	"""Hypothesis cannot await a test, so each example drives its own coroutine to completion."""
	return asyncio.run(coroutine)


def make_candidates(count: int) -> list[tuple[uuid.UUID, str, None, bool]]:
	return [(uuid.uuid4(), f"sk-{index}", None, False) for index in range(count)]


class Upstream:
	"""A fake provider: each call consumes the next scripted step, and every key it is called with is recorded."""

	def __init__(self, script: list[tuple[str, int | None]]) -> None:
		self.script = script
		self.keys_called: list[str] = []

	async def __call__(self, api_key: str, **_: Any) -> str:
		position = len(self.keys_called)
		self.keys_called.append(api_key)
		kind, code = self.script[position] if position < len(self.script) else ("fail", 503)
		if kind == "ok":
			return f"served-by-{api_key}"
		if kind == "http":
			raise HTTPException(status_code=code or 500, detail="gateway refused")
		raise provider_error(code or 500)


def expected_outcome(script: list[tuple[str, int | None]], count: int):
	"""An independent restatement of the loop: what should happen, call by call."""
	for index in range(count):
		kind, code = script[index] if index < len(script) else ("fail", 503)
		if kind == "ok":
			return ("served", index)
		if kind == "http":
			return ("http", index)
		if code not in _RETRYABLE_STATUS_CODES:
			return ("raised", index)
		if index == count - 1:
			return ("raised", index)
	raise AssertionError("unreachable")


# ── properties ───────────────────────────────────────────────────────────────


@SETTINGS
@given(script=scripts, count=st.integers(1, 6))
def test_a_retry_only_ever_calls_the_keys_it_was_given_in_order_and_at_most_once(script, count):
	candidates = make_candidates(count)
	upstream = Upstream(script)

	try:
		run(LLMService._execute_with_fallback(candidates, upstream, "openai/gpt-4o"))
	except Exception:  # noqa: BLE001 - the outcome is asserted by the other properties
		pass

	given_keys = [candidate[1] for candidate in candidates]
	assert upstream.keys_called == given_keys[: len(upstream.keys_called)]  # a prefix of the list, in order
	assert len(set(upstream.keys_called)) == len(upstream.keys_called)  # no key is tried twice
	assert set(upstream.keys_called) <= set(given_keys)  # nothing outside the list is ever called


@SETTINGS
@given(script=scripts, count=st.integers(1, 6))
def test_the_attempt_that_succeeds_is_the_one_reported_and_a_non_retryable_failure_stops_the_loop(script, count):
	candidates = make_candidates(count)
	upstream = Upstream(script)
	outcome, index = expected_outcome(script, count)

	if outcome == "served":
		response, fallbacks, winner = run(LLMService._execute_with_fallback(candidates, upstream, "openai/gpt-4o"))
		assert response == f"served-by-{candidates[index][1]}"
		assert (fallbacks, winner) == (index, candidates[index][0])
	elif outcome == "http":
		with pytest.raises(HTTPException) as raised:
			run(LLMService._execute_with_fallback(candidates, upstream, "openai/gpt-4o"))
		assert raised.value.status_code == 451
	else:
		with pytest.raises(Exception) as raised:
			run(LLMService._execute_with_fallback(candidates, upstream, "openai/gpt-4o"))
		expected_status = script[index][1] if index < len(script) else 503
		assert getattr(raised.value, "status_code", None) == expected_status

	assert len(upstream.keys_called) == index + 1  # it stopped exactly where the rules say


@SETTINGS
@given(count=st.integers(1, 6), code=st.sampled_from(RETRYABLE))
def test_when_every_key_fails_the_last_error_is_raised_after_trying_each_once(count, code):
	candidates = make_candidates(count)
	upstream = Upstream([("fail", code)] * count)

	with pytest.raises(Exception) as raised:
		run(LLMService._execute_with_fallback(candidates, upstream, "openai/gpt-4o"))

	assert raised.value.status_code == code  # type: ignore[attr-defined]
	assert len(upstream.keys_called) == count


@SETTINGS
@given(code=st.sampled_from(RETRYABLE + NON_RETRYABLE))
def test_only_the_documented_transient_statuses_are_retryable(code):
	assert _is_retryable(provider_error(code)) is (code in {429, 500, 502, 503, 504})


@pytest.mark.parametrize("exc", [Exception("no status"), ValueError("x"), TimeoutError()])
def test_an_error_without_a_status_is_not_retried(exc):
	assert _is_retryable(exc) is False


async def test_with_no_candidates_nothing_is_called_and_the_caller_gets_a_503():
	upstream = Upstream([("ok", None)])
	with pytest.raises(HTTPException) as raised:
		await LLMService._execute_with_fallback([], upstream, "openai/gpt-4o")
	assert raised.value.status_code == 503 and upstream.keys_called == []
