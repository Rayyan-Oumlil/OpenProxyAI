"""Evaluation datasets against the real schema: RLS, import rules and the admin API (Phase 3, slice 3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.database import org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.dataset import Dataset, DatasetItem
from tests.db_helpers import Api, make_user, remove_seeded_logs, seed  # noqa: F401  (an autouse fixture: removes seeded request_logs)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/datasets"


async def make_dataset(api, name="regression") -> str:
	created = await api.http.post(PATH, json={"name": name})
	assert created.status_code == 201, created.text
	return created.json()["id"]


async def imported_ids(org_id, dataset_id) -> set:
	async with org_scoped_session(org_id) as db:
		return set(await db.scalars(select(DatasetItem.request_id).where(DatasetItem.dataset_id == uuid.UUID(dataset_id))))


# -- the admin API --------------------------------------------------------------------------------


async def test_create_list_get_and_delete_a_dataset(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, "support-tickets")
		listed = (await api.http.get(PATH)).json()
		assert [(d["name"], d["item_count"]) for d in listed] == [("support-tickets", 0)]
		assert (await api.http.get(f"{PATH}/{dataset_id}")).json()["name"] == "support-tickets"
		assert (await api.http.delete(f"{PATH}/{dataset_id}")).status_code == 204
		assert (await api.http.get(f"{PATH}/{dataset_id}")).status_code == 404


async def test_a_duplicate_name_is_a_409_and_the_same_name_is_free_in_another_org(tenants):
	user_b = await make_user(tenants.b)
	async with Api(tenants.a, tenants.user_a) as api:
		await make_dataset(api, "shared-name")
		again = await api.http.post(PATH, json={"name": "shared-name"})
		assert again.status_code == 409 and again.json()["detail"]["error"] == "dataset_exists"
	async with Api(tenants.b, user_b) as api:
		assert (await api.http.post(PATH, json={"name": "shared-name"})).status_code == 201


async def test_only_admins_may_use_datasets(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
	async with Api(tenants.a, tenants.user_a, role="developer") as api:
		calls = [api.http.get(PATH), api.http.post(PATH, json={"name": "x"}), api.http.get(f"{PATH}/{dataset_id}"),
		         api.http.post(f"{PATH}/{dataset_id}/import", json={}), api.http.get(f"{PATH}/{dataset_id}/items")]
		assert [(await c).status_code for c in calls] == [403] * 5


async def test_another_orgs_dataset_does_not_exist_for_you(tenants):
	user_b = await make_user(tenants.b)
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, "private")
	async with Api(tenants.b, user_b) as api:
		assert (await api.http.get(PATH)).json() == []
		assert [(await c).status_code for c in (api.http.get(f"{PATH}/{dataset_id}"), api.http.delete(f"{PATH}/{dataset_id}"),
		                                        api.http.post(f"{PATH}/{dataset_id}/import", json={}),
		                                        api.http.get(f"{PATH}/{dataset_id}/items"))] == [404, 404, 404, 404]


async def test_creating_importing_and_deleting_are_in_the_admin_audit_log(tenants):
	await seed(tenants.a, tenants.user_a.id)
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, "audited")
		await api.http.post(f"{PATH}/{dataset_id}/import", json={})
		await api.http.delete(f"{PATH}/{dataset_id}")
	async with org_scoped_session(tenants.a) as db:
		actions = set(await db.scalars(select(AdminAuditLog.action).where(AdminAuditLog.org_id == tenants.a, AdminAuditLog.resource_type == "dataset")))
	assert actions == {"dataset.created", "dataset.imported", "dataset.deleted"}


# -- importing captured traffic ---------------------------------------------------------------------


async def test_an_import_copies_captured_requests_and_reports_what_it_did(tenants):
	first, second = await seed(tenants.a, tenants.user_a.id), await seed(tenants.a, tenants.user_a.id, content="Translate this.")
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		result = (await api.http.post(f"{PATH}/{dataset_id}/import", json={})).json()
		assert result == {"imported": 2, "skipped_redacted": 0, "skipped_duplicate": 0, "stopped_at_capacity": False}
		items = (await api.http.get(f"{PATH}/{dataset_id}/items")).json()
		assert {i["request_id"] for i in items} == {str(first), str(second)}
		assert all(i["output"] == "Revenue grew." and i["expected"] is None for i in items)
		assert (await api.http.get(f"{PATH}/{dataset_id}")).json()["item_count"] == 2


async def test_a_row_the_pii_detector_touched_is_never_imported(tenants):
	clean = await seed(tenants.a, tenants.user_a.id)
	await seed(tenants.a, tenants.user_a.id, redacted=True, content="mail [REDACTED]")
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		result = (await api.http.post(f"{PATH}/{dataset_id}/import", json={})).json()
	assert (result["imported"], result["skipped_redacted"]) == (1, 1)
	assert await imported_ids(tenants.a, dataset_id) == {clean}


async def test_every_row_is_scanned_again_so_pii_the_old_detector_missed_is_caught(tenants):
	"""A row stored unflagged but containing an email (as if the detector had improved since) is still refused."""
	await seed(tenants.a, tenants.user_a.id, content="reach me at jane.doe@example.com", redacted=False)
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		result = (await api.http.post(f"{PATH}/{dataset_id}/import", json={})).json()
	assert (result["imported"], result["skipped_redacted"]) == (0, 1) and await imported_ids(tenants.a, dataset_id) == set()


async def test_importing_twice_adds_nothing_the_second_time(tenants):
	await seed(tenants.a, tenants.user_a.id)
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		await api.http.post(f"{PATH}/{dataset_id}/import", json={})
		again = (await api.http.post(f"{PATH}/{dataset_id}/import", json={})).json()
	assert (again["imported"], again["skipped_duplicate"]) == (0, 1)


async def test_a_repeated_limited_import_moves_on_to_requests_it_has_not_copied_yet(tenants):
	"""Already-imported rows must be excluded before the limit applies, or a second import re-fetches the same newest rows."""
	for i in range(4):
		await seed(tenants.a, tenants.user_a.id, content=f"q{i}", age_days=i)
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		first = (await api.http.post(f"{PATH}/{dataset_id}/import", json={"limit": 2})).json()
		second = (await api.http.post(f"{PATH}/{dataset_id}/import", json={"limit": 2})).json()
		third = (await api.http.post(f"{PATH}/{dataset_id}/import", json={"limit": 2})).json()
	assert (first["imported"], second["imported"], third["imported"]) == (2, 2, 0)
	assert len(await imported_ids(tenants.a, dataset_id)) == 4


async def test_filters_by_model_age_and_score(tenants):
	user = tenants.user_a.id
	mini_recent = await seed(tenants.a, user, model="openai/gpt-4o-mini", score=("thumbs", 1))
	await seed(tenants.a, user, model="openai/gpt-4o", score=("thumbs", 1))
	await seed(tenants.a, user, model="openai/gpt-4o-mini", age_days=10, score=("thumbs", 1))
	await seed(tenants.a, user, model="openai/gpt-4o-mini", score=("thumbs", 0))
	await seed(tenants.a, user, model="openai/gpt-4o-mini")  # never rated
	since = (datetime.now(UTC) - timedelta(days=2)).isoformat()
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		result = await api.http.post(f"{PATH}/{dataset_id}/import", json={"model": "openai/gpt-4o-mini", "since": since, "score_name": "thumbs", "min_score": 1})
		assert result.status_code == 200 and result.json()["imported"] == 1
	assert await imported_ids(tenants.a, dataset_id) == {mini_recent}


async def test_the_limit_caps_an_import_and_random_order_still_stays_inside_the_matches(tenants):
	ids = {await seed(tenants.a, tenants.user_a.id, content=f"question {i}") for i in range(6)}
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		result = (await api.http.post(f"{PATH}/{dataset_id}/import", json={"limit": 3, "order": "random"})).json()
	assert result["imported"] == 3 and await imported_ids(tenants.a, dataset_id) <= ids


async def test_another_orgs_captured_traffic_is_never_imported(tenants):
	user_b = await make_user(tenants.b)
	await seed(tenants.b, user_b.id, content="org B secret question")
	mine = await seed(tenants.a, tenants.user_a.id)
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		result = (await api.http.post(f"{PATH}/{dataset_id}/import", json={})).json()
	assert result["imported"] == 1 and await imported_ids(tenants.a, dataset_id) == {mine}


async def test_a_dataset_stops_at_its_item_limit(tenants, monkeypatch):
	monkeypatch.setattr("app.services.dataset_service.MAX_ITEMS_PER_DATASET", 2)
	for i in range(4):
		await seed(tenants.a, tenants.user_a.id, content=f"q{i}")
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		first = (await api.http.post(f"{PATH}/{dataset_id}/import", json={})).json()
		second = (await api.http.post(f"{PATH}/{dataset_id}/import", json={})).json()
	assert (first["imported"], first["stopped_at_capacity"]) == (2, True)
	assert (second["imported"], second["stopped_at_capacity"]) == (0, True)


@pytest.mark.parametrize(
	"payload",
	[{"min_score": 1}, {"score_name": "t", "min_score": 5, "max_score": 1}, {"limit": 0}, {"limit": 1001},
	 {"order": "oldest"}, {"since": "2026-02-01T00:00:00Z", "until": "2026-01-01T00:00:00Z"}, {"surprise": 1}],
)
async def test_a_malformed_import_is_a_422(tenants, payload):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		assert (await api.http.post(f"{PATH}/{dataset_id}/import", json=payload)).status_code == 422


# -- items added by hand -----------------------------------------------------------------------------


async def test_an_item_can_be_added_by_hand_listed_and_deleted(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		added = await api.http.post(f"{PATH}/{dataset_id}/items", json={"messages": [{"role": "user", "content": "2+2?"}], "expected": "4"})
		assert added.status_code == 201, added.text
		item = added.json()
		assert (item["request_id"], item["expected"], item["messages"]) == (None, "4", [{"role": "user", "content": "2+2?"}])
		assert [i["id"] for i in (await api.http.get(f"{PATH}/{dataset_id}/items")).json()] == [item["id"]]
		assert (await api.http.delete(f"{PATH}/{dataset_id}/items/{item['id']}")).status_code == 204
		assert (await api.http.get(f"{PATH}/{dataset_id}/items")).json() == []
		assert (await api.http.delete(f"{PATH}/{dataset_id}/items/{item['id']}")).status_code == 404


async def test_an_item_with_personal_data_is_refused_not_rewritten(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		for body in (
			{"messages": [{"role": "user", "content": "my SSN is 123-45-6789"}]},
			{"messages": [{"role": "user", "content": "fine"}], "expected": "write to jane.doe@example.com"},
		):
			refused = await api.http.post(f"{PATH}/{dataset_id}/items", json=body)
			assert refused.status_code == 422 and refused.json()["detail"]["error"] == "pii_in_item"
		assert (await api.http.get(f"{PATH}/{dataset_id}")).json()["item_count"] == 0


@pytest.mark.parametrize(
	"body",
	[{"messages": []}, {"messages": [{"role": "tool", "content": "x"}]}, {"messages": [{"role": "user", "content": ["image"]}]},
	 {"messages": [{"role": "user", "content": "x"}], "surprise": 1}],
)
async def test_a_malformed_item_is_a_422(tenants, body):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		assert (await api.http.post(f"{PATH}/{dataset_id}/items", json=body)).status_code == 422


async def test_items_page_in_a_stable_order(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		for i in range(5):
			await api.http.post(f"{PATH}/{dataset_id}/items", json={"messages": [{"role": "user", "content": f"q{i}"}]})
		first = (await api.http.get(f"{PATH}/{dataset_id}/items", params={"limit": 2, "offset": 0})).json()
		rest = (await api.http.get(f"{PATH}/{dataset_id}/items", params={"limit": 50, "offset": 2})).json()
		everything = (await api.http.get(f"{PATH}/{dataset_id}/items", params={"limit": 50})).json()
	assert [i["id"] for i in first + rest] == [i["id"] for i in everything] and len(everything) == 5


async def test_deleting_a_dataset_deletes_its_items(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api)
		await api.http.post(f"{PATH}/{dataset_id}/items", json={"messages": [{"role": "user", "content": "q"}]})
		await api.http.delete(f"{PATH}/{dataset_id}")
	async with org_scoped_session(tenants.a) as db:
		assert await db.scalar(select(func.count()).select_from(DatasetItem)) == 0
		assert await db.scalar(select(func.count()).select_from(Dataset)) == 0
