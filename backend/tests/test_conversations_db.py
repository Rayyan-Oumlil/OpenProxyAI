"""Conversations against the real schema: RLS, who-sees-what inside an org, sharing, admin audit (Phase 4, slice 1).

The user-level rules (owner, teammate, admin) are application rules, because RLS separates orgs only. Each route is tried as
every kind of caller, so a route that forgot the rule fails here.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import insert, select

from app.database import SystemSessionLocal, org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.conversation import Conversation, ConversationTurn
from app.models.team import Team, team_members
from app.models.user import User
from app.services.policy_service import PolicyConfig, policy_store
from app.utils.crypto import hash_password
from tests.conftest import FakeRedis
from tests.db_helpers import Api, remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/conversations"


async def member(org_id, role="developer") -> SimpleNamespace:
	async with SystemSessionLocal() as session:
		user = User(org_id=org_id, email=f"c-{uuid.uuid4().hex[:8]}@test.local", password_hash=hash_password(uuid.uuid4().hex), role=role, is_active=True)
		session.add(user)
		await session.commit()
		return SimpleNamespace(id=user.id, email=user.email, role=role)


async def team_of(org_id, *users) -> uuid.UUID:
	async with SystemSessionLocal() as session:
		team = Team(org_id=org_id, name=f"team-{uuid.uuid4().hex[:6]}")
		session.add(team)
		await session.flush()
		for user in users:
			await session.execute(insert(team_members).values(team_id=team.id, user_id=user.id))
		await session.commit()
		return team.id


async def enable(org_id, api=None, on=True) -> None:
	async with org_scoped_session(org_id) as db:
		await policy_store.save(org_id, PolicyConfig(conversations_enabled=on), db, (api.redis if api else FakeRedis()))


def as_user(org_id, user, role=None) -> Api:
	return Api(org_id, user, role=role or user.role)


async def make(api, **body) -> dict:
	response = await api.http.post(PATH, json={"title": "Q3 review", **body})
	assert response.status_code == 201, response.text
	return response.json()


async def add_turns(org_id, conversation_id, *texts) -> None:
	async with org_scoped_session(org_id) as db:
		for seq, text in enumerate(texts, start=1):
			db.add(ConversationTurn(org_id=org_id, conversation_id=uuid.UUID(conversation_id), seq=seq, role="user" if seq % 2 else "assistant", content=text, data_class="internal"))
		await db.commit()


@pytest.fixture
async def org(tenants):
	"""Org A with conversations switched on, its admin, a developer owner and a second developer."""
	alice, bob = await member(tenants.a), await member(tenants.a)
	await enable(tenants.a)
	return SimpleNamespace(id=tenants.a, other=tenants.b, admin=tenants.user_a, alice=alice, bob=bob)


# -- the opt-in ---------------------------------------------------------------------------------


async def test_nothing_can_be_started_until_the_org_opts_in(tenants):
	alice = await member(tenants.a)
	async with as_user(tenants.a, alice) as api:
		refused = await api.http.post(PATH, json={"title": "hello"})
		assert refused.status_code == 403 and refused.json()["detail"]["error"] == "conversations_disabled"
		await enable(tenants.a, api)
		assert (await api.http.post(PATH, json={"title": "hello"})).status_code == 201


async def test_switching_it_off_keeps_existing_conversations_readable_and_deletable(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api)
		await enable(org.id, api, on=False)
		assert (await api.http.get(f"{PATH}/{created['id']}")).status_code == 200
		assert (await api.http.post(PATH, json={"title": "new"})).status_code == 403
		assert (await api.http.delete(f"{PATH}/{created['id']}")).status_code == 204


async def test_a_viewer_cannot_start_a_conversation(org):
	viewer = await member(org.id, "viewer")
	async with as_user(org.id, viewer) as api:
		assert (await api.http.post(PATH, json={"title": "x"})).status_code == 403


# -- the owner's own conversation ---------------------------------------------------------------


async def test_create_read_update_list_and_delete(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api, tags=["Finance", "finance", " Q3 "])
		assert created["visibility"] == "private" and created["is_owner"] and created["turn_count"] == 0
		assert created["tags"] == ["finance", "q3"]  # lower-cased and de-duplicated
		await add_turns(org.id, created["id"], "first", "second")

		got = (await api.http.get(f"{PATH}/{created['id']}")).json()
		assert got["turn_count"] == 2
		turns = (await api.http.get(f"{PATH}/{created['id']}/turns")).json()
		assert [(t["seq"], t["content"]) for t in turns] == [(1, "first"), (2, "second")]

		updated = (await api.http.patch(f"{PATH}/{created['id']}", json={"title": "Renamed", "tags": ["ops"]})).json()
		assert updated["title"] == "Renamed" and updated["tags"] == ["ops"] and updated["updated_at"] >= created["updated_at"]
		assert [c["id"] for c in (await api.http.get(PATH)).json()] == [created["id"]]

		assert (await api.http.delete(f"{PATH}/{created['id']}")).status_code == 204
		assert (await api.http.get(f"{PATH}/{created['id']}")).status_code == 404
		async with org_scoped_session(org.id) as db:  # the turns went with it
			assert (await db.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id == uuid.UUID(created["id"])))).first() is None


@pytest.mark.parametrize("body", [
	{"title": ""}, {"title": "x" * 201}, {"title": "ok", "tags": ["t"] * 11}, {"title": "ok", "tags": ["x" * 31]},
	{"title": "ok", "visibility": "public"}, {"title": "ok", "visibility": "team"}, {"title": "ok", "team_id": str(uuid.uuid4())},
	{"title": "ok", "owner_id": str(uuid.uuid4())}, {"title": "ok", "org_id": str(uuid.uuid4())},
])
async def test_invalid_input_is_a_422(org, body):
	async with as_user(org.id, org.alice) as api:
		assert (await api.http.post(PATH, json=body)).status_code == 422


async def test_a_user_keeps_at_most_a_set_number_of_conversations(org, monkeypatch):
	monkeypatch.setattr("app.routes.conversations.MAX_PER_USER", 2)
	async with as_user(org.id, org.alice) as api:
		await make(api)
		await make(api)
		full = await api.http.post(PATH, json={"title": "third"})
		assert full.status_code == 409 and full.json()["detail"]["error"] == "too_many_conversations"
	async with as_user(org.id, org.bob) as api:  # the cap is per user
		assert (await api.http.post(PATH, json={"title": "bob's"})).status_code == 201


# -- another user in the same org: a private conversation is private ------------------------------


async def test_every_route_treats_someone_elses_private_conversation_as_not_found(org):
	async with as_user(org.id, org.alice) as api:
		secret = await make(api, title="salary talks")
		await add_turns(org.id, secret["id"], "what everyone earns")
	path = f"{PATH}/{secret['id']}"
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(path)).status_code == 404
		assert (await api.http.get(f"{path}/turns")).status_code == 404
		assert (await api.http.patch(path, json={"title": "mine now"})).status_code == 404
		assert (await api.http.delete(path)).status_code == 404
		assert (await api.http.get(PATH)).json() == []
		assert (await api.http.get(PATH, params={"scope": "shared"})).json() == []
	async with as_user(org.id, org.alice) as api:  # nothing above changed it
		got = (await api.http.get(path)).json()
		assert got["title"] == "salary talks" and got["turn_count"] == 1


async def test_an_admin_sees_metadata_for_every_conversation_but_cannot_read_a_private_one(org):
	async with as_user(org.id, org.alice) as api:
		secret = await make(api, title="salary talks")
		await add_turns(org.id, secret["id"], "what everyone earns")
	async with as_user(org.id, org.admin, role="admin") as api:
		listed = (await api.http.get(PATH, params={"scope": "org"})).json()
		row = next(c for c in listed if c["id"] == secret["id"])
		assert row["owner_email"] == org.alice.email and row["turn_count"] == 1 and row["is_owner"] is False
		assert "content" not in str(listed)  # metadata only
		assert (await api.http.get(f"{PATH}/{secret['id']}")).status_code == 404
		assert (await api.http.get(f"{PATH}/{secret['id']}/turns")).status_code == 404
		assert (await api.http.patch(f"{PATH}/{secret['id']}", json={"title": "x"})).status_code == 404
		assert (await api.http.get(PATH)).json() == []  # "mine" is still only mine


async def test_only_an_admin_may_list_the_whole_org(org):
	async with as_user(org.id, org.alice) as api:
		assert (await api.http.get(PATH, params={"scope": "org"})).status_code == 403


async def test_an_admin_can_delete_one_and_it_is_audited_without_its_content(org):
	async with as_user(org.id, org.alice) as api:
		secret = await make(api, title="salary talks")
		await add_turns(org.id, secret["id"], "what everyone earns")
	async with as_user(org.id, org.admin, role="admin") as api:
		assert (await api.http.delete(f"{PATH}/{secret['id']}")).status_code == 204
	async with org_scoped_session(org.id) as db:
		audit = (await db.scalars(select(AdminAuditLog).where(AdminAuditLog.org_id == org.id, AdminAuditLog.action == "conversation.deleted"))).all()
		assert len(audit) == 1 and audit[0].resource_id == secret["id"]
		assert str(audit[0].after) and "what everyone earns" not in str(audit[0].after) and "salary talks" not in str(audit[0].after)
		assert audit[0].after["owner_id"] == str(org.alice.id)
		assert await db.get(Conversation, uuid.UUID(secret["id"])) is None


async def test_an_owner_deleting_their_own_is_not_an_admin_event(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api)
		await api.http.delete(f"{PATH}/{created['id']}")
	async with org_scoped_session(org.id) as db:
		assert (await db.scalars(select(AdminAuditLog).where(AdminAuditLog.org_id == org.id, AdminAuditLog.action == "conversation.deleted"))).first() is None


# -- sharing with a team ------------------------------------------------------------------------


async def test_a_teammate_can_read_a_shared_conversation_and_nothing_else(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		shared = await make(api, title="launch plan", visibility="team", team_id=str(team))
		await add_turns(org.id, shared["id"], "the plan")
	path = f"{PATH}/{shared['id']}"
	async with as_user(org.id, org.bob) as api:
		got = (await api.http.get(path)).json()
		assert got["title"] == "launch plan" and got["is_owner"] is False
		assert [t["content"] for t in (await api.http.get(f"{path}/turns")).json()] == ["the plan"]
		assert [c["id"] for c in (await api.http.get(PATH, params={"scope": "shared"})).json()] == [shared["id"]]
		assert (await api.http.get(PATH)).json() == []  # not "mine"
		assert (await api.http.patch(path, json={"title": "hijack"})).status_code == 404  # read-only
		assert (await api.http.patch(path, json={"visibility": "private"})).status_code == 404
		assert (await api.http.delete(path)).status_code == 404


async def test_a_user_outside_the_team_cannot_see_it(org):
	team = await team_of(org.id, org.alice)
	outsider = await member(org.id)
	async with as_user(org.id, org.alice) as api:
		shared = await make(api, visibility="team", team_id=str(team))
	async with as_user(org.id, outsider) as api:
		assert (await api.http.get(f"{PATH}/{shared['id']}")).status_code == 404
		assert (await api.http.get(f"{PATH}/{shared['id']}/turns")).status_code == 404
		assert (await api.http.get(PATH, params={"scope": "shared"})).json() == []


async def test_going_private_again_takes_access_away(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		shared = await make(api, visibility="team", team_id=str(team))
		back = (await api.http.patch(f"{PATH}/{shared['id']}", json={"visibility": "private"})).json()
		assert back["visibility"] == "private" and back["team_id"] is None
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(f"{PATH}/{shared['id']}")).status_code == 404


async def test_you_can_only_share_with_a_team_you_belong_to(org):
	not_mine = await team_of(org.id, org.bob)
	foreign_team = await team_of(org.other, await member(org.other))
	async with as_user(org.id, org.alice) as api:
		for team in (not_mine, foreign_team, uuid.uuid4()):
			refused = await api.http.post(PATH, json={"title": "x", "visibility": "team", "team_id": str(team)})
			assert refused.status_code == 422 and refused.json()["detail"]["error"] == "not_a_team_member"
		created = await make(api)
		assert (await api.http.patch(f"{PATH}/{created['id']}", json={"visibility": "team", "team_id": str(not_mine)})).status_code == 422
		assert (await api.http.patch(f"{PATH}/{created['id']}", json={"visibility": "team"})).status_code == 422  # needs a team
		assert (await api.http.get(f"{PATH}/{created['id']}")).json()["visibility"] == "private"  # unchanged


async def test_a_private_conversation_cannot_be_given_a_team(org):
	team = await team_of(org.id, org.alice)
	async with as_user(org.id, org.alice) as api:
		created = await make(api)
		bad = await api.http.patch(f"{PATH}/{created['id']}", json={"visibility": "private", "team_id": str(team)})
		assert bad.status_code == 422


async def test_deleting_a_team_unshares_its_conversations(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		shared = await make(api, visibility="team", team_id=str(team))
	async with SystemSessionLocal() as session:
		await session.delete(await session.get(Team, team))
		await session.commit()
	async with org_scoped_session(org.id) as db:
		assert await db.get(Conversation, uuid.UUID(shared["id"])) is not None  # the conversation stays
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(f"{PATH}/{shared['id']}")).status_code == 404  # nobody on the old team keeps access
	async with as_user(org.id, org.alice) as api:
		assert (await api.http.get(f"{PATH}/{shared['id']}")).json()["visibility"] == "private"  # and the owner sees it as private


# -- another org ---------------------------------------------------------------------------------


async def test_another_org_cannot_see_or_touch_a_conversation(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api)
	stranger = await member(org.other)
	async with as_user(org.other, stranger) as api:
		path = f"{PATH}/{created['id']}"
		assert (await api.http.get(path)).status_code == 404
		assert (await api.http.get(f"{path}/turns")).status_code == 404
		assert (await api.http.patch(path, json={"title": "x"})).status_code == 404
		assert (await api.http.delete(path)).status_code == 404
		assert (await api.http.get(PATH)).json() == []
	async with org_scoped_session(org.other) as db:  # and the database agrees, whatever the application said
		assert (await db.scalars(select(Conversation))).all() == []


async def test_the_database_refuses_a_row_for_a_different_org_than_the_session(org):
	async with org_scoped_session(org.other) as db:
		db.add(Conversation(org_id=org.id, owner_id=org.alice.id, title="smuggled"))
		with pytest.raises(Exception, match="row-level security"):
			await db.commit()


async def test_turn_order_is_unique_within_a_conversation(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api)
	await add_turns(org.id, created["id"], "one")
	with pytest.raises(Exception, match="uq_conversation_turns_seq"):
		await add_turns(org.id, created["id"], "again as seq 1")


# -- the helpers the console's pickers use ------------------------------------------------------------


async def test_my_teams_lists_only_teams_the_caller_belongs_to_in_their_org(org):
	mine = await team_of(org.id, org.alice)
	await team_of(org.id, org.bob)
	await team_of(org.other, await member(org.other))
	async with as_user(org.id, org.alice) as api:
		listed = (await api.http.get(f"{PATH}/teams")).json()
	assert [t["id"] for t in listed] == [str(mine)]


async def test_usable_models_are_the_enabled_ones_with_a_live_key_and_their_effective_clearance(org):
	from app.models.llm_provider_key import LLMProviderKey
	from app.models.model_registry import ModelRegistryEntry

	async with org_scoped_session(org.id) as db:
		key = LLMProviderKey(org_id=org.id, provider="openai", key_alias="k", api_key_encrypted="x", is_active=True, max_data_class="internal")
		dead = LLMProviderKey(org_id=org.id, provider="anthropic", key_alias="d", api_key_encrypted="x", is_active=False, max_data_class="secret")
		db.add_all([key, dead])
		await db.flush()
		db.add_all([
			ModelRegistryEntry(org_id=org.id, model_id="openai/gpt-4o", provider="openai", provider_key_id=key.id, max_data_class="confidential", regions=["us"], risk_rating="low", enabled=True),
			ModelRegistryEntry(org_id=org.id, model_id="anthropic/claude", provider="anthropic", provider_key_id=dead.id, max_data_class="secret", regions=["us"], risk_rating="low", enabled=True),
			ModelRegistryEntry(org_id=org.id, model_id="openai/off", provider="openai", provider_key_id=key.id, max_data_class="internal", regions=["us"], risk_rating="low", enabled=False),
		])
		await db.commit()
	async with as_user(org.id, org.alice) as api:
		listed = (await api.http.get(f"{PATH}/models")).json()
	assert listed == [{"model_id": "openai/gpt-4o", "max_data_class": "internal"}]  # the key's lower class wins


# -- org-wide sharing and personas ---------------------------------------------------------------------


async def test_only_an_admin_can_publish_a_conversation_to_the_whole_org(org):
	async with as_user(org.id, org.alice) as api:
		refused = await api.http.post(PATH, json={"title": "x", "visibility": "org"})
		assert refused.status_code == 403 and refused.json()["detail"]["error"] == "admin_only"
		mine = await make(api)
		assert (await api.http.patch(f"{PATH}/{mine['id']}", json={"visibility": "org"})).status_code == 403
	async with as_user(org.id, org.admin, role="admin") as api:
		published = await api.http.post(PATH, json={"title": "handbook Q&A", "visibility": "org"})
		assert published.status_code == 201 and published.json()["visibility"] == "org" and published.json()["team_id"] is None


async def test_an_org_conversation_is_readable_by_every_member_and_writable_by_none_but_its_owner(org):
	async with as_user(org.id, org.admin, role="admin") as api:
		shared = await make(api, visibility="org")
		await add_turns(org.id, shared["id"], "welcome", "hello")
	path = f"{PATH}/{shared['id']}"
	viewer = await member(org.id, "viewer")
	for reader in (org.alice, org.bob, viewer):
		async with as_user(org.id, reader) as api:
			assert (await api.http.get(path)).json()["is_owner"] is False
			assert [t["content"] for t in (await api.http.get(f"{path}/turns")).json()] == ["welcome", "hello"]
			assert shared["id"] in [c["id"] for c in (await api.http.get(PATH, params={"scope": "shared"})).json()]
			assert (await api.http.patch(path, json={"title": "hijack"})).status_code == 404
			assert (await api.http.delete(path)).status_code == 404
	stranger = await member(org.other)
	async with as_user(org.other, stranger) as api:
		assert (await api.http.get(path)).status_code == 404  # org-wide means this org, not every org


async def test_unpublishing_an_org_conversation_takes_access_away(org):
	async with as_user(org.id, org.admin, role="admin") as api:
		shared = await make(api, visibility="org")
		assert (await api.http.patch(f"{PATH}/{shared['id']}", json={"visibility": "private"})).json()["visibility"] == "private"
	async with as_user(org.id, org.alice) as api:
		assert (await api.http.get(f"{PATH}/{shared['id']}")).status_code == 404


async def test_an_org_conversation_cannot_carry_a_team(org):
	team = await team_of(org.id, org.admin)
	async with as_user(org.id, org.admin, role="admin") as api:
		assert (await api.http.post(PATH, json={"title": "x", "visibility": "org", "team_id": str(team)})).status_code == 422


async def test_a_persona_is_stored_returned_changed_and_cleared(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api, system_prompt="  You are a terse reviewer.  ")
		assert created["system_prompt"] == "You are a terse reviewer."
		changed = (await api.http.patch(f"{PATH}/{created['id']}", json={"system_prompt": "Answer in French."})).json()
		assert changed["system_prompt"] == "Answer in French."
		cleared = (await api.http.patch(f"{PATH}/{created['id']}", json={"system_prompt": None})).json()
		assert cleared["system_prompt"] is None
		assert (await api.http.post(PATH, json={"title": "x", "system_prompt": ""})).status_code == 422
		assert (await api.http.post(PATH, json={"title": "x", "system_prompt": "a" * 4_001})).status_code == 422
