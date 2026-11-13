# ruff: noqa: F811  (fixtures are imported from the suite that defines them and then used by name)
"""Behaviour settings on a conversation turn: what the provider receives and what the record of it says."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.database import org_scoped_session
from app.models.conversation import ConversationContextPackage
from app.services import behavior as bh
from app.services import conversation_turns as ct
from tests.db_helpers import Api, remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_conversation_turns_db import configure, org, say, start, upstream  # noqa: F401  (fixtures and helpers)
from tests.test_conversations_db import as_user
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


async def test_without_behaviour_a_turn_is_sent_exactly_as_before(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		response = await say(api, conversation, "Hello", temperature=0.9, max_tokens=500)
	assert response.status_code == 201 and "x-openproxyai-behavior" not in response.headers
	call = upstream.calls[0]
	assert (call["temperature"], call["max_tokens"]) == (0.9, 500) and "reasoning_effort" not in call
	assert "behavior" not in upstream.logs[0]["request_metadata"]


async def test_a_turn_setting_becomes_provider_parameters_and_is_recorded(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		response = await say(api, conversation, "Hello", behavior={"creativity": "low", "reasoning_depth": "high"})
	assert response.status_code == 201, response.text
	call = upstream.calls[0]
	assert call["temperature"] == bh.TEMPERATURE["low"] and "reasoning_effort" not in call  # gpt-4o takes no reasoning_effort
	assert response.headers["x-openproxyai-behavior"] == "creativity=low; reasoning_depth=high"
	recorded = upstream.logs[0]["request_metadata"]["behavior"]
	assert recorded["applied"] == {"temperature": bh.TEMPERATURE["low"]} and [i["param"] for i in recorded["ignored"]] == ["reasoning_effort"]


async def test_the_orgs_ceiling_lowers_a_turn(org, upstream):
	await configure(org.id, routing_mode="enforce", behavior_ceiling={"creativity": "low", "max_response_length": "short"})
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		response = await say(api, conversation, "Hello", behavior={"creativity": "high"}, temperature=2, max_tokens=20000)
	call = upstream.calls[0]
	assert (call["temperature"], call["max_tokens"]) == (bh.TEMPERATURE["low"], bh.MAX_TOKENS["short"])
	assert response.headers["x-openproxyai-behavior-clamped"] == "creativity"


async def test_an_invalid_setting_is_rejected_before_anything_is_sent(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api)
		response = await say(api, conversation, "Hello", behavior={"creativity": "wild"})
	assert response.status_code == 422 and upstream.calls == []


async def test_citations_join_the_system_prompt_and_the_record_of_what_was_sent_covers_them(org, upstream):
	async with as_user(org.id, org.alice) as api:
		conversation = await start(api, system_prompt="be brief")
		response = await say(api, conversation, "Hello", behavior={"citations": True})
	assert response.status_code == 201, response.text
	sent = upstream.calls[0]["messages"]
	assert sent[0]["role"] == "system" and sent[0]["content"].startswith("be brief") and bh.CITATION_INSTRUCTION in sent[0]["content"]
	async with org_scoped_session(org.id) as db:
		record = await db.scalar(select(ConversationContextPackage).where(ConversationContextPackage.conversation_id == uuid.UUID(conversation)))
	assert record.payload_sha256 == ct._sha256(sent)
