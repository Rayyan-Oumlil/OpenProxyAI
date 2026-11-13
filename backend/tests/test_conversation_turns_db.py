"""Conversation turns against the real schema with a fake upstream that records what it receives (Phase 4, slice 3).

The point of every test here is the same question: what did the provider actually get?
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from app.database import org_scoped_session
from app.models.conversation import Conversation, ConversationContextPackage, ConversationTurn
from app.services import conversation_turns as ct
from app.services import model_runner as mr
from app.services import rate_limiter
from app.services.llm_service import ProviderKeyCandidate, llm_service
from app.services.policy_service import PolicyConfig, policy_store
from app.services.routing_service import Candidate
from tests.conftest import FakeRedis
from tests.db_helpers import Api, remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_conversations_db import PATH, as_user, member, team_of
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

SECRET_TEXT = "Project Falcon: the acquisition price is 4.2 billion."
GPT, CLAUDE, MISTRAL = "openai/gpt-4o", "anthropic/claude-3-5-sonnet", "mistral/mistral-large"


def entry(model_id, level):
	return Candidate(
		model_id=model_id, provider=model_id.split("/")[0], enabled=True, key_id=uuid.uuid4(), key_active=True,
		key_class=level, entry_class=level, regions=("us",), risk="low",
	)


REGISTRY = [entry(GPT, "confidential"), entry(CLAUDE, "internal"), entry(MISTRAL, "internal")]


@pytest.fixture
def upstream(monkeypatch):
	"""The provider: records every call, answers from a script. Also stands in for key choice, cost and the audit log."""
	seen = SimpleNamespace(calls=[], logs=[], limit_checks=[], reply="Sure.", error=None, registry=REGISTRY)

	async def acompletion(**kwargs):
		seen.calls.append(kwargs)
		if seen.error:
			raise RuntimeError(seen.error)
		return SimpleNamespace(
			choices=[SimpleNamespace(message=SimpleNamespace(content=seen.reply))],
			usage=SimpleNamespace(prompt_tokens=11, completion_tokens=3),
		)

	async def select_keys(*_a, **_k):
		return [ProviderKeyCandidate(None, "sk-test", None)]

	async def log_request(**kwargs):
		seen.logs.append(kwargs)

	async def routing_inputs(db, org_id, config=None):
		return list(seen.registry), "us"

	async def allow(*_a, **kwargs):
		seen.limit_checks.append(kwargs)
		return (True, {}, None, None, None)

	monkeypatch.setattr(mr, "acompletion", acompletion)
	monkeypatch.setattr(mr, "log_request", log_request)
	monkeypatch.setattr(mr.cost_tracker_service, "calculate_cost_usd", lambda _r: 0)
	monkeypatch.setattr(llm_service, "_select_provider_keys", select_keys)
	monkeypatch.setattr(llm_service, "routing_inputs", routing_inputs)
	monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", allow)
	seen.sent_to = lambda model: [c for c in seen.calls if c["model"] == model]
	seen.everything_sent = lambda: json.dumps([c["messages"] for c in seen.calls], ensure_ascii=False)
	return seen


async def configure(org_id, **policy):
	async with org_scoped_session(org_id) as db:
		await policy_store.save(org_id, PolicyConfig(conversations_enabled=True, **policy), db, FakeRedis())


@pytest.fixture
async def org(tenants):
	alice, bob = await member(tenants.a), await member(tenants.a)
	await configure(tenants.a, routing_mode="enforce")
	return SimpleNamespace(id=tenants.a, other=tenants.b, admin=tenants.user_a, alice=alice, bob=bob)


async def start(api, **body):
	created = await api.http.post(PATH, json={"title": "t", **body})
	assert created.status_code == 201, created.text
	return created.json()["id"]


async def say(api, conversation, content, model=GPT, **extra):
	return await api.http.post(f"{PATH}/{conversation}/turns", json={"content": content, "model": model, **extra})


async def stored(org_id, conversation):
	async with org_scoped_session(org_id) as db:
		rows = await db.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id == uuid.UUID(conversation)).order_by(ConversationTurn.seq))
		return [(t.seq, t.role, t.data_class, t.content) for t in rows]


# -- the happy path -------------------------------------------------------------------------------


async def test_a_turn_is_answered_stored_and_audited_as_a_conversation_call(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		response = await say(api, conversation, "Hello there")
		assert response.status_code == 201, response.text
		body = response.json()
		assert body["assistant_turn"]["content"] == "Sure." and body["assistant_turn"]["model"] == GPT
		assert [body["user_turn"]["seq"], body["assistant_turn"]["seq"]] == [1, 2]
		assert body["context"]["withheld"] == [] and body["prompt_tokens"] == 11
		assert upstream.calls[0]["messages"] == [{"role": "user", "content": "Hello there"}]
		assert upstream.logs[0]["request_metadata"]["source"] == "conversation"
		assert upstream.logs[0]["request_metadata"]["conversation_id"] == conversation
		assert (await api.http.get(f"{PATH}/{conversation}")).json()["turn_count"] == 2


async def test_history_is_sent_in_order_and_follows_the_user_across_three_models(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		upstream.reply = "A1"
		await say(api, conversation, "Q1", model=GPT)
		upstream.reply = "A2"
		await say(api, conversation, "Q2", model=CLAUDE)
		upstream.reply = "A3"
		await say(api, conversation, "Q3", model=MISTRAL)
		await say(api, conversation, "Q4", model=GPT)
	assert [m["content"] for m in upstream.sent_to(GPT)[-1]["messages"]] == ["Q1", "A1", "Q2", "A2", "Q3", "A3", "Q4"]
	assert [m["content"] for m in upstream.sent_to(CLAUDE)[0]["messages"]] == ["Q1", "A1", "Q2"]


async def test_the_stored_copy_is_redacted_but_the_model_gets_what_the_user_typed(org, upstream):
	text_with_email = "Mail me at jane.doe@example.com about this"
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, text_with_email)
	assert text_with_email in upstream.everything_sent()
	rows = await stored(org.id, conversation)
	assert "jane.doe@example.com" not in rows[0][3] and rows[0][3] != text_with_email


# -- history is data too --------------------------------------------------------------------------


async def test_a_confidential_turn_never_reaches_a_model_cleared_only_for_internal_data(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		first = await say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")
		assert first.status_code == 201, first.text
		second = await say(api, conversation, "Now write a haiku about spring", model=CLAUDE)
		assert second.status_code == 201, second.text
		withheld = second.json()["context"]["withheld"]
	assert sorted(w["seq"] for w in withheld) == [1, 2] and {w["reason"] for w in withheld} == {"above_clearance"}
	received = json.dumps(upstream.sent_to(CLAUDE)[0]["messages"])
	assert "Falcon" not in received and "4.2 billion" not in received and "Sure." not in received
	assert upstream.sent_to(CLAUDE)[0]["messages"] == [{"role": "user", "content": "Now write a haiku about spring"}]


async def test_the_withheld_turns_are_named_in_the_stored_context_record_and_the_hash_matches_what_was_sent(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")
		answer = (await say(api, conversation, "next", model=CLAUDE)).json()
		record = (await api.http.get(f"{PATH}/{conversation}/turns/{answer['assistant_turn']['id']}/context")).json()
	assert record["model"] == CLAUDE and record["data_class"] == "internal" and record["routing_mode"] == "enforce"
	assert record["included_turn_ids"] == [] and len(record["withheld"]) == 2
	sent = upstream.sent_to(CLAUDE)[0]["messages"]
	import hashlib
	assert record["payload_sha256"] == hashlib.sha256(json.dumps(sent, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def test_an_answer_takes_the_class_of_everything_the_model_saw(org, upstream):
	"""A confidential question is in context, so even a harmless follow-up's answer may quote it: that answer is confidential too."""
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")
		upstream.reply = "Spring rain falls"
		await say(api, conversation, "Write a haiku", model=GPT)  # GPT is cleared for confidential, so it sees turn 1
		assert [(seq, cls) for seq, _, cls, _ in await stored(org.id, conversation)] == [(1, "confidential"), (2, "confidential"), (3, "internal"), (4, "confidential")]
		later = await say(api, conversation, "Anything else?", model=CLAUDE)
	assert later.json()["context"]["included_turn_ids"] == []  # the whole conversation stays withheld from the internal-only model
	assert "Falcon" not in json.dumps(upstream.sent_to(CLAUDE)[0]["messages"]) and "Spring rain" not in json.dumps(upstream.sent_to(CLAUDE)[0]["messages"])


async def test_a_new_message_above_the_models_clearance_is_refused_not_answered_blind(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		refused = await say(api, conversation, SECRET_TEXT, model=CLAUDE, data_class="confidential")
		assert refused.status_code == 446 and "not_authorized" in refused.json()["detail"]["detail"]
		assert (await api.http.get(f"{PATH}/{conversation}")).json()["turn_count"] == 0  # nothing stored
	assert upstream.calls == []  # nothing sent


async def test_even_if_the_context_builder_were_wrong_routing_still_refuses_the_package(org, upstream, monkeypatch):
	"""Defence in depth: the package's class goes through the same routing check as any request."""
	real = ct.build_context
	monkeypatch.setattr(ct, "build_context", lambda turns, msg, **kw: real(turns, msg, **{**kw, "clearance": 3}))
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")
		upstream.calls.clear()
		leak = await say(api, conversation, "write a haiku", model=CLAUDE)
	assert leak.status_code == 446
	assert upstream.calls == []


async def test_a_model_missing_from_the_registry_is_refused_when_enforcing(org, upstream):
	async with as_user(org.id, org.alice) as api:
		refused = await say(api, await start(api), "hi", model="openai/unknown-model")
	assert refused.status_code == 446 and upstream.calls == []


async def test_with_routing_off_every_turn_is_sent_as_today(org, upstream):
	await configure(org.id, routing_mode="off")
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")
		reply = await say(api, conversation, "next", model=CLAUDE)
	assert reply.json()["context"]["withheld"] == [] and "Falcon" in json.dumps(upstream.sent_to(CLAUDE)[0]["messages"])


async def test_log_only_never_refuses_and_records_that_it_did_not_enforce(org, upstream):
	await configure(org.id, routing_mode="log_only")
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")
		reply = await say(api, conversation, "next", model=CLAUDE)
	assert reply.status_code == 201 and reply.json()["context"]["routing_mode"] == "log_only"


async def test_the_context_budget_drops_whole_old_exchanges_and_says_so(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		for n in range(3):
			await say(api, conversation, f"question number {n} " + "x" * 200)
		reply = await say(api, conversation, "latest", max_context_tokens=150)
	assert {w["reason"] for w in reply.json()["context"]["withheld"]} == {"over_budget"}
	sent = [m["content"] for m in upstream.calls[-1]["messages"]]
	assert sent[-1] == "latest" and not any("question number 0" in m for m in sent)


# -- failure paths --------------------------------------------------------------------------------


async def test_an_upstream_failure_stores_nothing_records_the_attempt_and_never_tries_another_model(org, upstream):
	upstream.error = "provider exploded"
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		failed = await say(api, conversation, "hello", model=GPT)
		assert failed.status_code == 502 and failed.json()["detail"]["error"] == "model_error"
		assert (await api.http.get(f"{PATH}/{conversation}")).json()["turn_count"] == 0
	assert [c["model"] for c in upstream.calls] == [GPT]  # no silent fallback
	async with org_scoped_session(org.id) as db:
		packages = (await db.scalars(select(ConversationContextPackage).where(ConversationContextPackage.conversation_id == uuid.UUID(conversation)))).all()
	assert [p.outcome for p in packages] == ["error"] and failed.json()["detail"]["package_id"] == str(packages[0].id)


async def test_a_policy_block_is_a_refusal_and_nothing_is_stored_or_sent(org, upstream):
	await configure(org.id, routing_mode="enforce", enforcement_mode="enforce", blocked_keywords=["falcon"])
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		blocked = await say(api, conversation, SECRET_TEXT)
		assert blocked.status_code == 446
		assert (await api.http.get(f"{PATH}/{conversation}")).json()["turn_count"] == 0
	assert upstream.calls == []


async def test_a_second_message_while_one_is_being_answered_is_refused(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await api.redis.set(f"conversation-turn:{conversation}", "1", nx=True, ex=100)
		busy = await say(api, conversation, "hello")
		assert busy.status_code == 409 and busy.json()["detail"]["error"] == "turn_in_progress"
		await api.redis.delete(f"conversation-turn:{conversation}")
		assert (await say(api, conversation, "hello")).status_code == 201
		assert await api.redis.get(f"conversation-turn:{conversation}") is None  # released after the turn


async def test_the_lock_is_released_even_when_the_call_fails(org, upstream):
	upstream.error = "boom"
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, "hello")
		assert await api.redis.get(f"conversation-turn:{conversation}") is None


@pytest.mark.parametrize("body", [
	{"content": "", "model": GPT}, {"content": "   ", "model": GPT}, {"content": "hi", "model": "no-slash"},
	{"content": "hi", "model": "cap:summarize"}, {"content": "hi", "model": GPT, "data_class": "top-secret"},
	{"content": "hi", "model": GPT, "conversation_id": str(uuid.uuid4())}, {"content": "x" * 20_001, "model": GPT},
	{"content": "hi", "model": GPT, "temperature": 9},
])
async def test_invalid_input_is_a_422_and_nothing_is_sent(org, upstream, body):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		assert (await api.http.post(f"{PATH}/{conversation}/turns", json=body)).status_code == 422
	assert upstream.calls == []


async def test_the_asserted_class_can_only_raise_the_class(org, upstream):
	await configure(org.id, routing_mode="enforce", default_data_class="confidential")
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, "plain words", model=GPT, data_class="public")
	assert (await stored(org.id, conversation))[0][2] == "confidential"


# -- who may talk in a conversation ----------------------------------------------------------------


async def test_nobody_but_the_owner_can_add_a_turn_to_someone_elses_conversation(org, upstream):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		private = await start(api)
		shared = await start(api, visibility="team", team_id=str(team))
	async with as_user(org.id, org.bob) as api:
		assert (await say(api, private, "hi")).status_code == 404
		assert (await say(api, shared, "hi")).status_code == 404  # a teammate reads, never writes
	async with as_user(org.id, org.admin, role="admin") as api:
		assert (await say(api, private, "hi")).status_code == 404
	stranger = await member(org.other)
	async with as_user(org.other, stranger) as api:
		assert (await say(api, private, "hi")).status_code == 404
	assert upstream.calls == []


async def test_a_teammate_can_see_what_was_sent_for_a_shared_answer_but_an_outsider_cannot(org, upstream):
	team = await team_of(org.id, org.alice, org.bob)
	outsider = await member(org.id)
	async with as_user(org.id, org.alice) as api:
		shared = await start(api, visibility="team", team_id=str(team))
		answer = (await say(api, shared, "hi")).json()["assistant_turn"]["id"]
	url = f"{PATH}/{shared}/turns/{answer}/context"
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(url)).status_code == 200
	async with as_user(org.id, outsider) as api:
		assert (await api.http.get(url)).status_code == 404


async def test_turns_need_the_org_to_have_conversations_on_and_a_role_that_can_write(org, upstream):
	viewer = await member(org.id, "viewer")
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
	async with as_user(org.id, viewer) as api:
		assert (await say(api, conversation, "hi")).status_code == 403
	await configure(org.id, routing_mode="enforce")
	async with org_scoped_session(org.id) as db:
		await policy_store.save(org.id, PolicyConfig(conversations_enabled=False), db, FakeRedis())
	async with as_user(org.id, org.alice) as api:
		off = await say(api, conversation, "hi")
		assert off.status_code == 403 and off.json()["detail"]["error"] == "conversations_disabled"
	assert upstream.calls == []


# -- the append-only record -----------------------------------------------------------------------


async def test_the_context_record_cannot_be_rewritten_or_deleted_by_the_application(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, "hi")
	async with org_scoped_session(org.id) as db:
		with pytest.raises(Exception, match="permission denied"):
			await db.execute(text("UPDATE conversation_context_packages SET withheld = '[]'::jsonb"))
	async with org_scoped_session(org.id) as db:
		with pytest.raises(Exception, match="permission denied"):
			await db.execute(text("DELETE FROM conversation_context_packages"))


async def test_deleting_a_conversation_removes_its_turns_and_its_context_records(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, "hi")
		assert (await api.http.delete(f"{PATH}/{conversation}")).status_code == 204
	async with org_scoped_session(org.id) as db:
		assert (await db.scalars(select(ConversationContextPackage))).all() == []
		assert (await db.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id == uuid.UUID(conversation)))).all() == []
		assert await db.get(Conversation, uuid.UUID(conversation)) is None


async def test_a_stored_turn_with_an_unreadable_class_is_assumed_secret_and_never_reaches_a_lower_model(org, upstream):
	vault = entry("local/vault", "secret")
	upstream.registry = [*REGISTRY, vault]
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		async with org_scoped_session(org.id) as db:
			db.add(ConversationTurn(org_id=org.id, conversation_id=uuid.UUID(conversation), seq=1, role="user", content="odd", data_class="bogus"))
			await db.commit()
		low = await say(api, conversation, "hi", model=GPT)
		assert low.json()["context"]["included_turn_ids"] == [] and len(low.json()["context"]["withheld"]) == 1
		high = await say(api, conversation, "hi again", model="local/vault")
	assert high.json()["context"]["data_class"] == "secret"  # the audit record says what it was treated as


async def test_a_sensitive_system_prompt_counts_toward_the_class_the_model_must_be_cleared_for(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		refused = await say(api, conversation, "summarise", model=CLAUDE, system_prompt="The customer's SSN is 123-45-6789.")
		assert refused.status_code == 446
		assert upstream.calls == []
		allowed = await say(api, conversation, "summarise", model=GPT, system_prompt="The customer's SSN is 123-45-6789.")
		assert allowed.status_code == 201 and allowed.json()["context"]["data_class"] == "confidential"
		assert [cls for _, _, cls, _ in await stored(org.id, conversation)][-1] == "confidential"  # and so is the answer


async def test_the_rate_limit_is_checked_on_everything_that_is_sent_not_just_the_new_message(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, "a" * 4000)
		upstream.limit_checks.clear()
		await say(api, conversation, "hi", system_prompt="b" * 400)
	assert upstream.limit_checks[0]["request_tokens_estimate"] >= 1000 + 100  # the earlier exchange and the system prompt count


# -- personas and the log_only preview ----------------------------------------------------------------------


async def test_the_conversations_persona_is_sent_with_every_turn_and_a_turns_own_prompt_overrides_it(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api, system_prompt="You are a terse reviewer.")
		await say(api, conversation, "first")
		await say(api, conversation, "second", system_prompt="Answer in French.")
	assert upstream.calls[0]["messages"][0] == {"role": "system", "content": "You are a terse reviewer."}
	assert upstream.calls[1]["messages"][0] == {"role": "system", "content": "Answer in French."}
	assert [m["content"] for m in upstream.calls[1]["messages"][1:]] == ["first", "Sure.", "second"]  # the persona is not stored as a turn


async def test_a_sensitive_persona_is_classified_like_any_system_prompt_and_can_be_refused(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api, system_prompt="The customer's SSN is 123-45-6789.")
		refused = await say(api, conversation, "summarise", model=CLAUDE)
		assert refused.status_code == 446
	assert upstream.calls == []


async def test_under_log_only_everything_is_sent_but_the_record_says_what_enforcement_would_have_held_back(org, upstream):
	await configure(org.id, routing_mode="log_only")
	upstream.registry = REGISTRY
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")
		reply = (await say(api, conversation, "next", model=CLAUDE)).json()["context"]
	assert reply["withheld"] == [] and "Falcon" in json.dumps(upstream.sent_to(CLAUDE)[0]["messages"])  # log_only never restricts
	assert sorted(w["seq"] for w in reply["would_withhold"]) == [1, 2] and {w["reason"] for w in reply["would_withhold"]} == {"above_clearance"}


async def test_under_enforce_there_is_no_preview_because_the_real_list_is_the_answer(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		await say(api, conversation, SECRET_TEXT, model=GPT, data_class="confidential")
		reply = (await say(api, conversation, "next", model=CLAUDE)).json()["context"]
	assert len(reply["withheld"]) == 2 and reply["would_withhold"] == []
