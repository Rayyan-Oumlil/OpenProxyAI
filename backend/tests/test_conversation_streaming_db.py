# ruff: noqa: F811
"""Streaming a conversation turn: the same guards as a whole turn, delivered as server-sent events (against the real schema)."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.database import org_scoped_session
from app.models.conversation import Conversation, ConversationContextPackage
from app.services import conversation_turns as ct
from app.services import model_runner as mr
from app.services.policy_service import policy_store
from tests.conftest import FakeRedis
from tests.db_helpers import remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_conversations_db import PATH, as_user
from tests.test_conversation_turns_db import CLAUDE, GPT, SECRET_TEXT, configure, org, start, upstream  # noqa: F401  (fixtures and helpers)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


def parse_sse(text):
	events = []
	for block in text.strip().split("\n\n"):
		lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
		events.append((lines["event"], json.loads(lines["data"])))
	return events


@pytest.fixture
def streaming(upstream, monkeypatch):  # noqa: F811
	"""The provider as a stream of chunks, recording what it was asked and able to break part-way."""
	seen = SimpleNamespace(parts=["Hello", " there", "!"], fail_after=None, calls=[])

	async def acompletion(**kwargs):
		seen.calls.append(kwargs)
		assert kwargs["stream"] is True and kwargs["stream_options"] == {"include_usage": True}

		async def chunks():
			for i, part in enumerate(seen.parts):
				if seen.fail_after is not None and i >= seen.fail_after:
					raise RuntimeError("stream broke")
				yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=part))], usage=None)
			yield SimpleNamespace(choices=[], usage=SimpleNamespace(prompt_tokens=9, completion_tokens=3))

		return chunks()

	monkeypatch.setattr(mr, "acompletion", acompletion)
	monkeypatch.setattr(mr.litellm, "stream_chunk_builder", lambda chunks, messages=None: object())
	return seen


async def stream_say(api, conversation, content, model=GPT, **extra):
	return await api.http.post(f"{PATH}/{conversation}/turns", json={"content": content, "model": model, "stream": True, **extra})


async def test_a_streamed_turn_sends_the_context_then_the_text_as_it_is_written_then_the_stored_exchange(org, streaming):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		response = await stream_say(api, conversation, "hi")
		assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
		events = parse_sse(response.text)
		assert [e for e, _ in events] == ["context", "delta", "delta", "delta", "done"]
		assert "".join(d["text"] for e, d in events if e == "delta") == "Hello there!"
		done = events[-1][1]
		assert done["assistant_turn"]["content"] == "Hello there!" and done["prompt_tokens"] == 9 and done["context"]["outcome"] == "ok"
		assert [t["content"] for t in (await api.http.get(f"{PATH}/{conversation}/turns")).json()] == ["hi", "Hello there!"]
		assert await api.redis.get(f"conversation-turn:{conversation}") is None  # the lock is released when the stream ends


async def test_a_streamed_turn_withholds_history_exactly_like_a_whole_one_and_says_so_first(org, upstream, streaming):  # noqa: F811
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		first = parse_sse((await stream_say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")).text)
		assert first[-1][0] == "done"
		events = parse_sse((await stream_say(api, conversation, "next", model=CLAUDE)).text)
	assert events[0][0] == "context" and sorted(w["seq"] for w in events[0][1]["withheld"]) == [1, 2]
	assert "Falcon" not in json.dumps(streaming.calls[1]["messages"]) and streaming.calls[1]["messages"][-1]["content"] == "next"


async def test_a_refusal_is_a_normal_446_before_any_stream_starts_and_nothing_is_stored(org, streaming):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		refused = await stream_say(api, conversation, SECRET_TEXT, model=CLAUDE, data_class="confidential")
		assert refused.status_code == 446 and refused.headers["content-type"].startswith("application/json")
		assert (await api.http.get(f"{PATH}/{conversation}")).json()["turn_count"] == 0
		assert await api.redis.get(f"conversation-turn:{conversation}") is None
	assert streaming.calls == []


async def test_a_stream_that_breaks_midway_ends_with_an_error_event_stores_nothing_and_records_the_attempt(org, streaming):
	streaming.fail_after = 1
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		events = parse_sse((await stream_say(api, conversation, "hi")).text)
		assert [e for e, _ in events] == ["context", "delta", "error"] and events[-1][1]["error"] == "model_error"
		assert (await api.http.get(f"{PATH}/{conversation}")).json()["turn_count"] == 0  # half an answer is not a turn
		assert await api.redis.get(f"conversation-turn:{conversation}") is None
	async with org_scoped_session(org.id) as db:
		packages = (await db.scalars(select(ConversationContextPackage).where(ConversationContextPackage.conversation_id == uuid.UUID(conversation)))).all()
	assert [p.outcome for p in packages] == ["error"]


async def test_the_audit_row_for_a_stream_carries_the_usage_and_the_conversation_source(org, upstream, streaming):  # noqa: F811
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await stream_say(api, conversation, "hi")
	row = upstream.logs[0]
	assert row["status_code"] == 200 and (row["prompt_tokens"], row["completion_tokens"]) == (9, 3)
	assert row["request_metadata"]["source"] == "conversation" and row["request_metadata"]["conversation_id"] == conversation


async def test_a_caller_who_disconnects_mid_stream_stores_nothing_and_the_abandoned_call_is_still_audited(org, upstream, streaming):  # noqa: F811
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		async with org_scoped_session(org.id) as db:
			policy = await policy_store.load(org.id, db, FakeRedis())
			row = await db.get(Conversation, uuid.UUID(conversation))
			prepared = await ct.begin_turn(db, api.redis, conversation=row, user_id=org.alice.id, model=GPT, content="hi", asserted_class=None, policy=policy)
		generator = ct.stream_turn(prepared, api.redis)
		assert (await generator.__anext__())[0] == "context"
		assert (await generator.__anext__())[0] == "delta"
		await generator.aclose()  # the client went away
		assert (await api.http.get(f"{PATH}/{conversation}")).json()["turn_count"] == 0
	assert [r["status_code"] for r in upstream.logs] == [mr.CLIENT_GONE_STATUS]


async def test_streaming_is_refused_for_an_org_that_checks_answers_because_they_cannot_be_checked_before_delivery(org, streaming):
	await configure(org.id, routing_mode="enforce", response_guardrails_enabled=True)
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		refused = await stream_say(api, conversation, "hi")
		assert refused.status_code == 422 and refused.json()["detail"]["error"] == "streaming_unavailable"
		assert await api.redis.get(f"conversation-turn:{conversation}") is None
	assert streaming.calls == []


async def test_a_second_message_while_a_stream_is_running_is_refused(org, streaming):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await api.redis.set(f"conversation-turn:{conversation}", "1", nx=True, ex=100)
		assert (await stream_say(api, conversation, "hi")).status_code == 409


async def test_the_lock_is_renewed_while_the_answer_is_written_and_released_only_by_its_owner(org, streaming):
	renewals = []
	async with as_user(org.id, org.alice) as api:
		real = api.redis.expire

		async def spy(key, seconds):
			renewals.append((key, seconds))
			return await real(key, seconds)

		api.redis.expire = spy
		conversation = await start(api)
		response = await stream_say(api, conversation, "hi")
		assert response.status_code == 200
		assert len(renewals) == 3 and all(k == f"conversation-turn:{conversation}" for k, _ in renewals)  # once per piece of text
		assert await api.redis.get(f"conversation-turn:{conversation}") is None


async def test_a_turn_never_releases_a_lock_that_another_turn_now_holds(org, streaming):
	"""If a lock expired mid-answer and a second turn took it, the first turn finishing must not free the second's lock."""
	from app.routes import conversations as routes

	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		key = f"conversation-turn:{conversation}"
		await api.redis.set(key, "another-turns-token", nx=True, ex=100)
		await routes._release(api.redis, key, "my-own-token")
		assert await api.redis.get(key) == "another-turns-token"
		await routes._release(api.redis, key, "another-turns-token")
		assert await api.redis.get(key) is None


async def test_an_abandoned_or_broken_stream_is_priced_from_its_tokens_never_at_zero(org, upstream, streaming, monkeypatch):  # noqa: F811
	monkeypatch.setattr(mr.litellm, "cost_per_token", lambda model, prompt_tokens, completion_tokens: (prompt_tokens * 0.001, completion_tokens * 0.002))
	streaming.fail_after = 1
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await stream_say(api, conversation, "hi")  # breaks after one piece
	row = upstream.logs[0]
	assert row["status_code"] == 502 and row["cost_usd"] > 0  # a broken stream was still generated, and charged


async def test_when_a_stream_cannot_be_priced_at_all_the_flat_fallback_is_charged_not_zero(org, upstream, streaming, monkeypatch):  # noqa: F811
	def unknown(**_k):
		raise ValueError("model not in the price map")

	monkeypatch.setattr(mr.litellm, "cost_per_token", unknown)
	monkeypatch.setattr(mr.settings, "UNPRICED_CALL_COST_USD", 0.07)
	streaming.fail_after = 1
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await stream_say(api, conversation, "hi")
	assert float(upstream.logs[0]["cost_usd"]) == 0.07


async def test_a_disconnect_is_priced_too(org, upstream, streaming, monkeypatch):  # noqa: F811
	monkeypatch.setattr(mr.litellm, "cost_per_token", lambda model, prompt_tokens, completion_tokens: (0.5, 0.5))
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		async with org_scoped_session(org.id) as db:
			policy = await policy_store.load(org.id, db, FakeRedis())
			row = await db.get(Conversation, uuid.UUID(conversation))
			prepared = await ct.begin_turn(db, api.redis, conversation=row, user_id=org.alice.id, model=GPT, content="hi", asserted_class=None, policy=policy)
		generator = ct.stream_turn(prepared, api.redis)
		await generator.__anext__()
		await generator.__anext__()
		await generator.aclose()
		assert len(upstream.logs) == 1  # audited by the time aclose() returns, not later
	assert upstream.logs[0]["status_code"] == mr.CLIENT_GONE_STATUS and float(upstream.logs[0]["cost_usd"]) == 1.0
