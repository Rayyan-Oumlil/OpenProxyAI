"""Reading scores back, against the real schema: isolation, roles, filters and aggregates (Phase 5, slice 5.12)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.database import org_scoped_session
from app.models.request_score import RequestScore
from tests.db_helpers import Api, make_user, remove_seeded_logs, seed  # noqa: F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/scores"


async def score(org_id, request_id, name, value, *, source="api", comment=None, age_days=0, user_id=None):
	async with org_scoped_session(org_id) as db:
		db.add(RequestScore(
			request_id=request_id, org_id=org_id, score_name=name, value=value, source=source, comment=comment, user_id=user_id,
			created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=age_days),
		))
		await db.commit()


@pytest.fixture
async def data(tenants):
	"""Org A: three models, a few scores each. Org B: a score on a request id that org A also uses (a collision must not leak)."""
	user = tenants.user_a
	mini, full = await seed(tenants.a, user.id, model="openai/gpt-4o-mini"), await seed(tenants.a, user.id, model="openai/gpt-4o")
	await score(tenants.a, mini, "thumbs", 1, comment="loved it", user_id=user.id)
	await score(tenants.a, mini, "quality", 4)
	await score(tenants.a, full, "thumbs", 0)
	other_user = await make_user(tenants.b)
	await seed(tenants.b, other_user.id, model="openai/secret-model", request_id=mini)  # same request id, another org
	await score(tenants.b, mini, "thumbs", 0, comment="org b only")
	return tenants, mini, full


async def get(tenants, path, params=None, role="admin"):
	async with Api(tenants.a, tenants.user_a, role=role) as api:
		return await api.http.get(path, params=params)


async def test_an_admin_lists_scores_with_their_model_comments_and_users(data):
	tenants, mini, full = data
	response = await get(tenants, PATH)
	assert response.status_code == 200
	rows = {(r["score_name"], r["model"]): r for r in response.json()}
	assert set(rows) == {("thumbs", "openai/gpt-4o-mini"), ("quality", "openai/gpt-4o-mini"), ("thumbs", "openai/gpt-4o")}
	assert rows[("thumbs", "openai/gpt-4o-mini")]["comment"] == "loved it" and rows[("thumbs", "openai/gpt-4o-mini")]["user_id"] == str(tenants.user_a.id)


async def test_another_orgs_scores_never_appear_even_on_a_shared_request_id(data):
	tenants, mini, _ = data
	listed = (await get(tenants, PATH)).json()
	assert "org b only" not in str(listed) and "openai/secret-model" not in str(listed)
	summary = (await get(tenants, f"{PATH}/summary", {"group_by": "model"})).json()
	assert "openai/secret-model" not in str(summary)
	assert {g["group"] for g in summary["groups"]} == {"openai/gpt-4o-mini", "openai/gpt-4o"}


async def test_filters_narrow_the_list(data):
	tenants, mini, full = data
	assert {r["score_name"] for r in (await get(tenants, PATH, {"score_name": "quality"})).json()} == {"quality"}
	assert {r["model"] for r in (await get(tenants, PATH, {"model": "openai/gpt-4o"})).json()} == {"openai/gpt-4o"}
	assert [r["request_id"] for r in (await get(tenants, PATH, {"request_id": str(full)})).json()] == [str(full)]
	assert (await get(tenants, PATH, {"source": "console"})).json() == []
	assert len((await get(tenants, PATH, {"limit": 1})).json()) == 1


async def test_only_an_admin_may_list_individual_scores(data):
	tenants, *_ = data
	for role in ("developer", "viewer"):
		assert (await get(tenants, PATH, role=role)).status_code == 403


async def test_a_summary_aggregates_by_name_model_or_day_and_carries_no_comments_or_users(data):
	tenants, *_ = data
	by_name = {g["group"]: g for g in (await get(tenants, f"{PATH}/summary", role="developer")).json()["groups"]}
	assert by_name["thumbs"]["count"] == 2 and by_name["thumbs"]["mean"] == 0.5 and (by_name["thumbs"]["min"], by_name["thumbs"]["max"]) == (0, 1)
	assert by_name["quality"] == {"group": "quality", "count": 1, "mean": 4.0, "min": 4.0, "max": 4.0}
	by_model = {g["group"]: g for g in (await get(tenants, f"{PATH}/summary", {"group_by": "model", "score_name": "thumbs"})).json()["groups"]}
	assert by_model["openai/gpt-4o-mini"]["mean"] == 1.0 and by_model["openai/gpt-4o"]["mean"] == 0.0
	by_day = (await get(tenants, f"{PATH}/summary", {"group_by": "day"})).json()["groups"]
	assert len(by_day) == 1 and by_day[0]["count"] == 3
	text = str((await get(tenants, f"{PATH}/summary")).json())
	assert "loved it" not in text and str(tenants.user_a.id) not in text


async def test_a_viewer_cannot_read_summaries(data):
	tenants, *_ = data
	assert (await get(tenants, f"{PATH}/summary", role="viewer")).status_code == 403


async def test_the_window_defaults_to_thirty_days_and_is_capped_at_a_year(data):
	tenants, mini, _ = data
	await score(tenants.a, mini, "old", 1, age_days=60)
	assert "old" not in {r["score_name"] for r in (await get(tenants, PATH)).json()}
	since = (datetime.now(UTC) - timedelta(days=90)).isoformat()
	assert "old" in {r["score_name"] for r in (await get(tenants, PATH, {"since": since})).json()}
	too_long = (datetime.now(UTC) - timedelta(days=400)).isoformat()
	assert (await get(tenants, PATH, {"since": too_long})).status_code == 422
	future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
	assert (await get(tenants, PATH, {"since": future})).status_code == 422


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"offset": -1}, {"source": "nobody"}, {"request_id": "not-a-uuid"}])
async def test_bad_parameters_are_422s(data, params):
	tenants, *_ = data
	assert (await get(tenants, PATH, params)).status_code == 422


async def test_a_score_whose_request_log_is_gone_is_still_listed_with_no_model(data):
	tenants, *_ = data
	await score(tenants.a, uuid.uuid4(), "orphan", 1)
	rows = [r for r in (await get(tenants, PATH, {"score_name": "orphan"})).json()]
	assert len(rows) == 1 and rows[0]["model"] is None
	groups = (await get(tenants, f"{PATH}/summary", {"group_by": "model", "score_name": "orphan"})).json()["groups"]
	assert groups[0]["group"] == "unknown"
