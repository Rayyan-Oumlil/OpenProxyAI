# ruff: noqa: F811
"""An admin's organization-wide listing is metadata: it must never show a persona the admin could not read (found by the security review)."""

from __future__ import annotations

from tests.db_helpers import remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_conversations_db import PATH, as_user, make, org, team_of  # noqa: F401  (fixtures and helpers)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


async def test_the_admins_org_listing_never_shows_a_persona_it_could_not_read(org):
	team = await team_of(org.id, org.alice)
	async with as_user(org.id, org.alice) as api:
		private = await make(api, title="private one", system_prompt="PRIVATE-PERSONA")
		teamed = await make(api, title="team one", system_prompt="TEAM-PERSONA", visibility="team", team_id=str(team))
	async with as_user(org.id, org.admin, role="admin") as api:
		published = await make(api, title="org one", system_prompt="ORG-PERSONA", visibility="org")
		rows = {c["id"]: c for c in (await api.http.get(PATH, params={"scope": "org"})).json()}
	assert rows[private["id"]]["system_prompt"] is None and rows[teamed["id"]]["system_prompt"] is None  # the admin is neither owner nor teammate
	assert rows[published["id"]]["system_prompt"] == "ORG-PERSONA"
	assert "PRIVATE-PERSONA" not in str(rows) and "TEAM-PERSONA" not in str(rows)
