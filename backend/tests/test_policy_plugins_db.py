"""WebAssembly policy plugins against the real schema: upload rules, isolation, and what they do to a policy decision (Phase 5, slice 5.11)."""

from __future__ import annotations

import base64
import json

import pytest

wasmtime = pytest.importorskip("wasmtime")

from sqlalchemy import select, text  # noqa: E402

from app.database import SystemSessionLocal, org_scoped_session  # noqa: E402
from app.models.admin_audit_log import AdminAuditLog  # noqa: E402
from app.models.policy_plugin import PolicyPlugin  # noqa: E402
from app.schemas.chat import ChatCompletionRequest  # noqa: E402
from app.services import policy_plugins, wasm_runtime  # noqa: E402
from app.services.policy_service import policy_service, policy_store  # noqa: E402
from tests.conftest import FakeRedis  # noqa: E402
from tests.db_helpers import Api, make_user, remove_seeded_logs  # noqa: E402, F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: E402, F401  (shared DB test setup)
from tests.test_wasm_runtime import ALLOW_ALL, BLOCK_ALL, BLOCK_X, ENDLESS, WANTS_IMPORT  # noqa: E402

PATH = "/api/v1/policy-plugins"


def b64(data: bytes) -> str:
	return base64.b64encode(data).decode()


async def upload(api, name="no-x", module=BLOCK_X, **extra):
	return await api.http.post(PATH, json={"name": name, "module_b64": b64(module), **extra})


async def loaded_policy(org_id, mode="enforce", **fields):
	"""The org's policy as the request path would load it, with enforcement set."""
	async with org_scoped_session(org_id) as db:
		config = await policy_store.load(org_id, db, FakeRedis())
		config.enforcement_mode = mode
		for key, value in fields.items():
			setattr(config, key, value)
		await policy_store.save(org_id, config, db, FakeRedis())
		return await policy_store.load(org_id, db, FakeRedis())


@pytest.fixture(autouse=True)
def clean_cache():
	policy_plugins.forget()
	yield
	policy_plugins.forget()


# -- upload ----------------------------------------------------------------------------------------


async def test_a_valid_plugin_is_stored_hashed_listed_and_added_to_the_orgs_policy(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		created = await upload(api)
		assert created.status_code == 201, created.text
		body = created.json()
		assert body["sha256"] == wasm_runtime.sha256_of(BLOCK_X) and body["size_bytes"] == len(BLOCK_X) and body["enabled"] is True
		assert [p["name"] for p in (await api.http.get(PATH)).json()] == ["no-x"]
	policy = await loaded_policy(tenants.a)
	assert policy.wasm_plugins == [{"id": body["id"], "name": "no-x", "sha256": body["sha256"]}] and policy.org_id == tenants.a


@pytest.mark.parametrize("body,reason", [
	({"module_b64": "%%%not base64%%%"}, "base64"), ({"module_b64": b64(b"not a wasm module")}, "not a valid"),
	({"module_b64": b64(WANTS_IMPORT)}, "imports"), ({"module_b64": b64(ENDLESS)}, "time allowance"),
])
async def test_a_module_that_breaks_the_contract_is_refused_with_the_reason(tenants, body, reason):
	async with Api(tenants.a, tenants.user_a) as api:
		response = await api.http.post(PATH, json={"name": "bad", **body})
		assert response.status_code == 422 and response.json()["detail"]["error"] == "invalid_plugin" and reason in response.json()["detail"]["detail"]
		assert (await api.http.get(PATH)).json() == []


@pytest.mark.parametrize("name", ["", "Has Spaces", "UPPER", "-leading", "trailing-", "x" * 61, "semi;colon", "../etc"])
async def test_a_plugin_name_must_be_plain(tenants, name):
	async with Api(tenants.a, tenants.user_a) as api:
		assert (await upload(api, name=name)).status_code == 422


async def test_a_duplicate_name_is_a_409_and_an_org_has_a_limited_number_of_plugins(tenants, monkeypatch):
	monkeypatch.setattr(policy_plugins, "MAX_PLUGINS_PER_ORG", 2)
	async with Api(tenants.a, tenants.user_a) as api:
		assert (await upload(api, name="one")).status_code == 201
		again = await upload(api, name="one")
		assert again.status_code == 409 and again.json()["detail"]["error"] == "plugin_exists"
		assert (await upload(api, name="two", module=ALLOW_ALL)).status_code == 201
		full = await upload(api, name="three", module=BLOCK_ALL)
		assert full.status_code == 409 and full.json()["detail"]["error"] == "too_many_plugins"


async def test_an_oversized_upload_is_refused_before_it_is_decoded(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		response = await api.http.post(PATH, json={"name": "big", "module_b64": "A" * (wasm_runtime.MAX_MODULE_BYTES * 2)})
		assert response.status_code == 422


@pytest.mark.parametrize("role", ["developer", "viewer"])
async def test_only_an_admin_can_manage_plugins(tenants, role):
	async with Api(tenants.a, tenants.user_a) as admin:
		plugin_id = (await upload(admin)).json()["id"]
	async with Api(tenants.a, tenants.user_a, role=role) as api:
		assert (await api.http.get(PATH)).status_code == 403
		assert (await upload(api, name="other")).status_code == 403
		assert (await api.http.patch(f"{PATH}/{plugin_id}", json={"enabled": False})).status_code == 403
		assert (await api.http.delete(f"{PATH}/{plugin_id}")).status_code == 403


async def test_another_orgs_admin_cannot_see_change_or_remove_a_plugin(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		plugin_id = (await upload(api)).json()["id"]
	other = await make_user(tenants.b)
	async with Api(tenants.b, other) as api:
		assert (await api.http.get(PATH)).json() == []
		assert (await api.http.patch(f"{PATH}/{plugin_id}", json={"enabled": False})).status_code == 404
		assert (await api.http.delete(f"{PATH}/{plugin_id}")).status_code == 404
	assert (await loaded_policy(tenants.b)).wasm_plugins == []  # org B's policy never lists org A's plugin
	assert len((await loaded_policy(tenants.a)).wasm_plugins) == 1


async def test_changes_are_audited_with_the_hash_and_never_the_module(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		plugin_id = (await upload(api)).json()["id"]
		await api.http.patch(f"{PATH}/{plugin_id}", json={"enabled": False})
		await api.http.delete(f"{PATH}/{plugin_id}")
	async with org_scoped_session(tenants.a) as db:
		rows = (await db.scalars(select(AdminAuditLog).where(AdminAuditLog.org_id == tenants.a, AdminAuditLog.resource_type == "policy_plugin").order_by(AdminAuditLog.created_at))).all()
	assert [r.action for r in rows] == ["policy_plugin.uploaded", "policy_plugin.disabled", "policy_plugin.deleted"]
	assert all(r.after["sha256"] == wasm_runtime.sha256_of(BLOCK_X) for r in rows) and "AGFzbQ" not in json.dumps([r.after for r in rows])


async def test_the_policy_endpoint_cannot_be_used_to_list_a_plugin_the_upload_rules_never_saw(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		fake = {"id": "00000000-0000-0000-0000-000000000001", "name": "sneaky", "sha256": "0" * 64}
		response = await api.http.patch("/api/v1/organizations/current/policy", json={"wasm_plugins": [fake], "enforcement_mode": "enforce"})
		assert response.status_code == 200
	assert (await loaded_policy(tenants.a)).wasm_plugins == []


# -- the decision ---------------------------------------------------------------------------------------


async def decide(config, content):
	return await policy_service.evaluate_chat_request(ChatCompletionRequest(model="openai/gpt-4o", messages=[{"role": "user", "content": content}]), config)


async def test_a_plugin_blocks_what_it_says_and_only_that_under_enforce(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api)
	config = await loaded_policy(tenants.a, "enforce")
	blocked = await decide(config, "this has an X in it")
	assert blocked.allowed is False and blocked.reason_code == "wasm_plugin:no-x" and blocked.triggered_rules == ["wasm_plugin"]
	assert (await decide(config, "this is fine")).allowed is True


async def test_under_log_only_a_plugin_hit_is_recorded_but_not_enforced_and_off_never_asks(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api)
	flagged = await decide(await loaded_policy(tenants.a, "log_only"), "an X")
	assert flagged.allowed is True and flagged.action == "log_only" and flagged.reason_code == "wasm_plugin:no-x"
	assert (await decide(await loaded_policy(tenants.a, "off"), "an X")).action == "allow"


async def test_a_plugin_can_only_add_a_restriction_never_lift_one(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api, name="allow-all", module=ALLOW_ALL)
	config = await loaded_policy(tenants.a, "enforce", blocked_keywords=["forbidden"])
	blocked = await decide(config, "a forbidden word")
	assert blocked.allowed is False and blocked.reason_code == "blocked_keyword"  # the built-in rule decided; the plugin was not even asked


async def test_the_built_in_rules_decide_first_so_their_reason_is_the_one_reported(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api, name="block-all", module=BLOCK_ALL)
	config = await loaded_policy(tenants.a, "enforce", blocked_keywords=["forbidden"])
	assert (await decide(config, "forbidden")).reason_code == "blocked_keyword"
	assert (await decide(config, "clean")).reason_code == "wasm_plugin:block-all"


async def test_a_disabled_plugin_is_not_asked_and_a_deleted_one_is_gone(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		plugin_id = (await upload(api)).json()["id"]
		await api.http.patch(f"{PATH}/{plugin_id}", json={"enabled": False})
		assert (await decide(await loaded_policy(tenants.a, "enforce"), "an X")).allowed is True
		await api.http.patch(f"{PATH}/{plugin_id}", json={"enabled": True})
		assert (await decide(await loaded_policy(tenants.a, "enforce"), "an X")).allowed is False
		await api.http.delete(f"{PATH}/{plugin_id}")
		assert (await decide(await loaded_policy(tenants.a, "enforce"), "an X")).allowed is True


async def test_a_plugin_that_fails_at_runtime_is_a_violation_never_a_silent_allow(tenants, monkeypatch):
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api)

	def broken(data, text_):
		raise wasm_runtime.WasmError("the plugin crashed (a WebAssembly trap)")

	monkeypatch.setattr(wasm_runtime, "evaluate", broken)
	blocked = await decide(await loaded_policy(tenants.a, "enforce"), "perfectly innocent")
	assert blocked.allowed is False and blocked.reason_code == "wasm_plugin_error:no-x" and "could not give a verdict" in blocked.detail
	flagged = await decide(await loaded_policy(tenants.a, "log_only"), "perfectly innocent")
	assert flagged.allowed is True and flagged.reason_code == "wasm_plugin_error:no-x"


async def test_an_unexpected_bug_in_the_plugin_path_is_also_a_violation_not_an_allow(tenants, monkeypatch):
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api)

	def explodes(data, text_):
		raise RuntimeError("bug in the host")

	monkeypatch.setattr(wasm_runtime, "evaluate", explodes)
	assert (await decide(await loaded_policy(tenants.a, "enforce"), "x")).reason_code == "wasm_plugin_error:no-x"


async def test_a_stored_module_that_no_longer_matches_the_hash_in_the_policy_is_refused(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api)
	async with SystemSessionLocal() as session:  # someone with database access swaps the module for another
		await session.execute(text("UPDATE policy_plugins SET module = :m WHERE org_id = :o"), {"m": ALLOW_ALL, "o": tenants.a})
		await session.commit()
	policy_plugins.forget()
	blocked = await decide(await loaded_policy(tenants.a, "enforce"), "innocent")
	assert blocked.allowed is False and blocked.reason_code == "wasm_plugin_error:no-x"


async def test_text_too_long_for_a_plugin_to_judge_is_refused_under_enforce_not_judged_in_part(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api, name="allow-all", module=ALLOW_ALL)
	blocked = await decide(await loaded_policy(tenants.a, "enforce"), "a" * (wasm_runtime.MAX_INPUT_BYTES + 10))
	assert blocked.allowed is False and blocked.reason_code == "wasm_plugin_error:allow-all"


async def test_the_database_refuses_a_module_over_the_size_cap_or_empty(tenants):
	for size in (0, wasm_runtime.MAX_MODULE_BYTES + 1):
		async with org_scoped_session(tenants.a) as db:
			db.add(PolicyPlugin(org_id=tenants.a, name=f"s{size}", module=b"x", sha256="0" * 64, size_bytes=size))
			with pytest.raises(Exception, match="ck_policy_plugins_size"):
				await db.commit()


async def test_a_policy_served_from_the_cache_still_knows_its_org_and_so_still_asks_the_plugins(tenants):
	"""The policy is cached for a minute; losing the org on that path would silently turn plugins off for every cached request."""
	async with Api(tenants.a, tenants.user_a) as api:
		await upload(api)
	redis = FakeRedis()
	async with org_scoped_session(tenants.a) as db:
		config = await policy_store.load(tenants.a, db, redis)
		config.enforcement_mode = "enforce"
		await policy_store.save(tenants.a, config, db, redis)
		first = await policy_store.load(tenants.a, db, redis)  # from the database, and now cached
		second = await policy_store.load(tenants.a, db, redis)  # from the cache
	assert first.org_id == second.org_id == tenants.a
	assert (await decide(second, "an X")).allowed is False
