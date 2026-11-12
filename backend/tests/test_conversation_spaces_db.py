"""Tags, search, the "private" tag and project spaces, against the real schema.

A space is a folder. It never widens who can read a conversation: listing a space shows only conversations the caller could
already read, and every route that reads or changes a conversation keeps its owner / team / visibility rule. RLS separates orgs
only, so each route is tried as the people who must not get through.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.database import org_scoped_session
from app.models.space import Space
from app.models.team import Team
from tests.db_helpers import remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_conversations_db import PATH, add_turns, as_user, enable, make, member, team_of
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

SPACES = "/api/v1/spaces"


@pytest.fixture
async def org(tenants):
	"""Org A with conversations switched on, its admin, and two developers (alice and bob)."""
	alice, bob = await member(tenants.a), await member(tenants.a)
	await enable(tenants.a)
	return SimpleNamespace(id=tenants.a, other=tenants.b, admin=tenants.user_a, alice=alice, bob=bob)


async def make_space(api, **body) -> dict:
	response = await api.http.post(SPACES, json={"name": f"Space {uuid.uuid4().hex[:6]}", **body})
	assert response.status_code == 201, response.text
	return response.json()


# -- tags: validation and normalisation ---------------------------------------------------------


async def test_tags_are_trimmed_lowercased_collapsed_and_deduplicated(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api, tags=["  Q3   Review ", "q3 review", "Ops", "OPS"])
		assert created["tags"] == ["q3 review", "ops"]


@pytest.mark.parametrize("bad", [["a,b"], ["x" * 31], [""], ["   "], ["line\nbreak"], ["tab\there"], ["<script>"], [f"t{i}" for i in range(11)]])
async def test_bad_tags_are_refused(org, bad):
	async with as_user(org.id, org.alice) as api:
		response = await api.http.post(PATH, json={"title": "x", "tags": bad})
		assert response.status_code == 422, bad


async def test_tags_can_be_replaced_and_cleared(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api, tags=["finance"])
		changed = await api.http.patch(f"{PATH}/{created['id']}", json={"tags": ["ops", "q4"]})
		assert changed.json()["tags"] == ["ops", "q4"]
		cleared = await api.http.patch(f"{PATH}/{created['id']}", json={"tags": []})
		assert cleared.json()["tags"] == []


# -- tag filter and text search -----------------------------------------------------------------


async def test_filter_by_tag_is_exact_and_case_insensitive(org):
	async with as_user(org.id, org.alice) as api:
		a = await make(api, title="A", tags=["finance"])
		await make(api, title="B", tags=["finance-eu"])
		await make(api, title="C", tags=[])
		hits = (await api.http.get(PATH, params={"tag": "FINANCE"})).json()
		assert [h["id"] for h in hits] == [a["id"]]


async def test_search_matches_titles_and_tags_only_never_message_content(org):
	async with as_user(org.id, org.alice) as api:
		by_title = await make(api, title="Falcon budget", tags=[])
		by_tag = await make(api, title="Other", tags=["falcon"])
		by_content = await make(api, title="Unrelated", tags=[])
		await add_turns(org.id, by_content["id"], "Project Falcon price?", "About 4.2 billion.")
		hits = {h["id"] for h in (await api.http.get(PATH, params={"q": "falcon"})).json()}
		assert hits == {by_title["id"], by_tag["id"]}  # the conversation that only mentions it in a message is not found


async def test_search_treats_wildcards_literally(org):
	async with as_user(org.id, org.alice) as api:
		await make(api, title="plain title")
		percent = await make(api, title="100% sure")
		assert [h["id"] for h in (await api.http.get(PATH, params={"q": "%"})).json()] == [percent["id"]]
		assert (await api.http.get(PATH, params={"q": "_"})).json() == []


async def test_search_and_filters_never_reach_what_the_caller_cannot_read(org):
	async with as_user(org.id, org.bob) as bob_api:
		secret = await make(bob_api, title="Falcon plan", tags=["falcon"])  # private to bob
	async with as_user(org.id, org.alice) as api:
		for scope in ("mine", "shared"):
			hits = (await api.http.get(PATH, params={"scope": scope, "q": "falcon"})).json()
			assert secret["id"] not in {h["id"] for h in hits}
			hits = (await api.http.get(PATH, params={"scope": scope, "tag": "falcon"})).json()
			assert secret["id"] not in {h["id"] for h in hits}


async def test_the_org_listing_searches_metadata_for_admins_only(org):
	async with as_user(org.id, org.alice) as api:
		mine = await make(api, title="Falcon", tags=["falcon"])
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(PATH, params={"scope": "org", "q": "falcon"})).status_code == 403
	async with as_user(org.id, org.admin) as api:
		hits = (await api.http.get(PATH, params={"scope": "org", "q": "falcon"})).json()
		assert [h["id"] for h in hits] == [mine["id"]]
		assert (await api.http.get(f"{PATH}/{mine['id']}/turns")).status_code == 404  # still metadata only


# -- the "private" quick tag --------------------------------------------------------------------


async def test_a_conversation_created_with_the_private_tag_is_private(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api, tags=["Private"])
		assert created["visibility"] == "private" and created["tags"] == ["private"]


async def test_sharing_a_conversation_that_carries_the_private_tag_is_refused_not_ignored(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		response = await api.http.post(PATH, json={"title": "x", "tags": ["private"], "visibility": "team", "team_id": str(team)})
		assert response.status_code == 422 and response.json()["detail"]["error"] == "private_tag"
		created = await make(api, tags=["private"])
		response = await api.http.patch(f"{PATH}/{created['id']}", json={"visibility": "team", "team_id": str(team)})
		assert response.status_code == 422 and response.json()["detail"]["error"] == "private_tag"


async def test_adding_the_private_tag_to_a_shared_conversation_pulls_it_back_to_private(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		created = await make(api, visibility="team", team_id=str(team))
	async with as_user(org.id, org.bob) as bob:
		assert (await bob.http.get(f"{PATH}/{created['id']}")).status_code == 200
	async with as_user(org.id, org.alice) as api:
		changed = (await api.http.patch(f"{PATH}/{created['id']}", json={"tags": ["private"]})).json()
		assert changed["visibility"] == "private" and changed["team_id"] is None
	async with as_user(org.id, org.bob) as bob:
		assert (await bob.http.get(f"{PATH}/{created['id']}")).status_code == 404
		assert (await bob.http.get(f"{PATH}/{created['id']}/turns")).status_code == 404


async def test_removing_the_private_tag_does_not_share_anything(org):
	async with as_user(org.id, org.alice) as api:
		created = await make(api, tags=["private"])
		changed = (await api.http.patch(f"{PATH}/{created['id']}", json={"tags": []})).json()
		assert changed["visibility"] == "private"


async def test_the_whole_org_share_is_also_blocked_by_the_private_tag(org):
	async with as_user(org.id, org.admin) as api:
		response = await api.http.post(PATH, json={"title": "x", "tags": ["private"], "visibility": "org"})
		assert response.status_code == 422 and response.json()["detail"]["error"] == "private_tag"


# -- spaces: who sees a space -------------------------------------------------------------------


async def test_a_personal_space_is_visible_only_to_its_owner(org):
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, name="Personal")
		assert space["team_id"] is None and space["is_owner"]
		assert [s["id"] for s in (await api.http.get(SPACES)).json()] == [space["id"]]
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(SPACES)).json() == []


async def test_a_team_space_is_visible_to_the_team_and_nobody_else(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, team_id=str(team))
	async with as_user(org.id, org.bob) as api:
		listed = (await api.http.get(SPACES)).json()
		assert [s["id"] for s in listed] == [space["id"]] and listed[0]["is_owner"] is False
	outsider = await member(org.id)
	async with as_user(org.id, outsider) as api:
		assert (await api.http.get(SPACES)).json() == []
	async with as_user(org.id, org.admin) as api:  # an admin is not a member of every team
		assert (await api.http.get(SPACES)).json() == []


async def test_a_space_cannot_be_given_to_a_team_you_are_not_in(org):
	team = await team_of(org.id, org.bob)
	async with as_user(org.id, org.alice) as api:
		response = await api.http.post(SPACES, json={"name": "x", "team_id": str(team)})
		assert response.status_code == 422 and response.json()["detail"]["error"] == "not_a_team_member"


async def test_a_space_in_another_org_is_invisible_even_by_id(org):
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api)
	other_user = await member(org.other)
	async with as_user(org.other, other_user) as api:
		assert (await api.http.get(SPACES)).json() == []
		assert (await api.http.patch(f"{SPACES}/{space['id']}", json={"name": "hijack"})).status_code == 404
		assert (await api.http.delete(f"{SPACES}/{space['id']}")).status_code == 404
		await enable(org.other, api)
		put = await api.http.post(PATH, json={"title": "x", "space_id": space["id"]})
		assert put.status_code == 422 and put.json()["detail"]["error"] == "space_not_available"


async def test_rls_keeps_spaces_apart_at_the_database(org):
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api)
	async with org_scoped_session(org.other) as db:
		assert (await db.scalars(select(Space).where(Space.id == uuid.UUID(space["id"])))).first() is None


async def test_space_names_are_validated_and_unique_per_owner(org):
	async with as_user(org.id, org.alice) as api:
		for bad in ("", "   ", "x" * 101):
			assert (await api.http.post(SPACES, json={"name": bad})).status_code == 422
		await make_space(api, name="Roadmap")
		clash = await api.http.post(SPACES, json={"name": "roadmap"})
		assert clash.status_code == 409
	async with as_user(org.id, org.bob) as api:
		await make_space(api, name="Roadmap")  # someone else may use the same name


async def test_only_the_owner_renames_or_deletes_a_space(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, team_id=str(team))
	for user in (org.bob, org.admin):
		async with as_user(org.id, user) as api:
			assert (await api.http.patch(f"{SPACES}/{space['id']}", json={"name": "mine now"})).status_code == 404
			assert (await api.http.delete(f"{SPACES}/{space['id']}")).status_code == 404
	async with as_user(org.id, org.alice) as api:
		assert (await api.http.patch(f"{SPACES}/{space['id']}", json={"name": "Renamed"})).json()["name"] == "Renamed"


async def test_a_viewer_cannot_create_a_space(org):
	viewer = await member(org.id, "viewer")
	async with as_user(org.id, viewer) as api:
		assert (await api.http.post(SPACES, json={"name": "x"})).status_code == 403


# -- spaces hold conversations, but never widen who can read them -------------------------------


async def test_a_conversation_can_be_put_in_a_space_only_by_its_owner_and_a_space_the_owner_can_see(org):
	async with as_user(org.id, org.bob) as api:
		bobs_space = await make_space(api, name="Bob only")
	async with as_user(org.id, org.alice) as api:
		mine = await make(api, title="mine")
		refused = await api.http.patch(f"{PATH}/{mine['id']}", json={"space_id": bobs_space["id"]})
		assert refused.status_code == 422 and refused.json()["detail"]["error"] == "space_not_available"
		own = await make_space(api)
		put = await api.http.patch(f"{PATH}/{mine['id']}", json={"space_id": own["id"]})
		assert put.json()["space_id"] == own["id"]
		taken_out = await api.http.patch(f"{PATH}/{mine['id']}", json={"space_id": None})
		assert taken_out.json()["space_id"] is None
		assert (await api.http.post(PATH, json={"title": "new", "space_id": bobs_space["id"]})).status_code == 422


async def test_a_teammate_sees_only_what_they_could_already_read_inside_a_shared_space(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, team_id=str(team))
		shared = await make(api, title="shared one", visibility="team", team_id=str(team), space_id=space["id"])
		private = await make(api, title="private one", space_id=space["id"])
		tagged = await make(api, title="tagged private", tags=["private"], space_id=space["id"])
	async with as_user(org.id, org.bob) as api:
		in_space = (await api.http.get(PATH, params={"scope": "shared", "space_id": space["id"]})).json()
		assert [c["id"] for c in in_space] == [shared["id"]]
		assert private["id"] not in {c["id"] for c in in_space} and tagged["id"] not in {c["id"] for c in in_space}
		mine_in_space = (await api.http.get(PATH, params={"scope": "mine", "space_id": space["id"]})).json()
		assert mine_in_space == []


async def test_every_conversation_route_refuses_a_space_mate_for_a_private_conversation(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, team_id=str(team))
		private = await make(api, space_id=space["id"])
		await add_turns(org.id, private["id"], "secret", "answer")
	cid = private["id"]
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(f"{PATH}/{cid}")).status_code == 404
		assert (await api.http.get(f"{PATH}/{cid}/turns")).status_code == 404
		assert (await api.http.patch(f"{PATH}/{cid}", json={"title": "x", "space_id": None})).status_code == 404
		assert (await api.http.post(f"{PATH}/{cid}/turns", json={"model": "openai/gpt-4o", "content": "hi"})).status_code == 404
		assert (await api.http.get(f"{PATH}/{cid}/turns/{uuid.uuid4()}/context")).status_code == 404
		assert (await api.http.delete(f"{PATH}/{cid}")).status_code == 404
	async with as_user(org.id, org.admin) as api:
		assert (await api.http.get(f"{PATH}/{cid}/turns")).status_code == 404
		listed = (await api.http.get(PATH, params={"scope": "org", "space_id": space["id"]})).json()
		assert [c["id"] for c in listed] == [cid]  # metadata only


async def test_a_team_visible_conversation_in_a_space_stays_read_only_for_the_teammate(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, team_id=str(team))
		shared = await make(api, visibility="team", team_id=str(team), space_id=space["id"])
		await add_turns(org.id, shared["id"], "hello", "world")
	cid = shared["id"]
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(f"{PATH}/{cid}")).status_code == 200
		assert (await api.http.get(f"{PATH}/{cid}/turns")).status_code == 200  # the existing team rule, unchanged
		assert (await api.http.patch(f"{PATH}/{cid}", json={"space_id": None})).status_code == 404
		assert (await api.http.post(f"{PATH}/{cid}/turns", json={"model": "openai/gpt-4o", "content": "hi"})).status_code == 404
		assert (await api.http.delete(f"{PATH}/{cid}")).status_code == 404


async def test_a_space_you_can_read_a_conversation_of_but_not_see_is_not_revealed(org):
	async with as_user(org.id, org.admin) as admin_api:
		space = await make_space(admin_api, name="Admin private space")
		published = await make(admin_api, visibility="org", space_id=space["id"])
		assert published["space_id"] == space["id"]
	async with as_user(org.id, org.alice) as api:
		seen = (await api.http.get(f"{PATH}/{published['id']}")).json()
		assert seen["space_id"] is None and seen["space_name"] is None  # readable, but its folder is not alice's to see
		assert (await api.http.get(PATH, params={"scope": "shared", "space_id": space["id"]})).json() == []


async def test_a_spaces_conversation_count_never_includes_what_the_caller_cannot_read(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, team_id=str(team))
		await make(api, title="shared", visibility="team", team_id=str(team), space_id=space["id"])
		await make(api, title="mine only 1", space_id=space["id"])
		await make(api, title="mine only 2", space_id=space["id"])
		assert [s["conversation_count"] for s in (await api.http.get(SPACES)).json()] == [3]
	async with as_user(org.id, org.bob) as api:
		assert [s["conversation_count"] for s in (await api.http.get(SPACES)).json()] == [1]  # not 3: the count must not reveal private ones


async def test_deleting_a_space_keeps_its_conversations(org):
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api)
		conv = await make(api, space_id=space["id"])
		assert (await api.http.delete(f"{SPACES}/{space['id']}")).status_code == 204
		got = (await api.http.get(f"{PATH}/{conv['id']}")).json()
		assert got["space_id"] is None


async def test_deleting_the_team_turns_its_space_personal(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, team_id=str(team))
	from app.database import SystemSessionLocal
	async with SystemSessionLocal() as session:
		await session.delete(await session.get(Team, team))
		await session.commit()
	async with as_user(org.id, org.bob) as api:
		assert (await api.http.get(SPACES)).json() == []
	async with as_user(org.id, org.alice) as api:
		mine = (await api.http.get(SPACES)).json()
		assert [s["id"] for s in mine] == [space["id"]] and mine[0]["team_id"] is None


async def test_a_conversation_filter_by_space_needs_a_visible_space(org):
	async with as_user(org.id, org.bob) as api:
		bobs = await make_space(api)
		await make(api, title="in bobs", space_id=bobs["id"])
	async with as_user(org.id, org.alice) as api:
		assert (await api.http.get(PATH, params={"space_id": bobs["id"]})).json() == []
		assert (await api.http.get(PATH, params={"space_id": "not-a-uuid"})).status_code == 422


async def test_changing_a_conversations_team_share_does_not_move_it_between_spaces(org):
	team = await team_of(org.id, org.alice, org.bob)
	async with as_user(org.id, org.alice) as api:
		space = await make_space(api, team_id=str(team))
		conv = await make(api, space_id=space["id"])
		shared = (await api.http.patch(f"{PATH}/{conv['id']}", json={"visibility": "team", "team_id": str(team)})).json()
		assert shared["space_id"] == space["id"] and shared["space_name"] == space["name"]


async def test_the_count_of_spaces_per_user_is_bounded(org):
	async with as_user(org.id, org.alice) as api:
		for i in range(50):
			assert (await api.http.post(SPACES, json={"name": f"s{i}"})).status_code == 201
		over = await api.http.post(SPACES, json={"name": "one too many"})
		assert over.status_code == 409 and over.json()["detail"]["error"] == "too_many_spaces"


