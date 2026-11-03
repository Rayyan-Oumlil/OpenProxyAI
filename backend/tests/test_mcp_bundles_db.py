"""Virtual bundles against the real schema: RLS, constraints, cascades, resolution, admin API."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from app.database import org_scoped_session
from app.models.api_key import ApiKey
from app.models.mcp_bundle import ApiKeyMcpBundle, McpBundle, McpBundleTool
from app.services.mcp_bundles import key_has_bundles, load_bundle_patterns
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


async def make_key(tenants) -> uuid.UUID:
	org_id = tenants.a
	async with org_scoped_session(org_id) as db:
		key = ApiKey(user_id=tenants.user_a.id, org_id=org_id, key_hash=f"hash-{uuid.uuid4().hex}", key_prefix="opai_t",
		             permissions=["proxy:llm", "proxy:mcp"])
		db.add(key)
		await db.commit()
		return key.id


async def make_bundle(org_id, slug="readonly", tools=("github__search",), active=True) -> uuid.UUID:
	async with org_scoped_session(org_id) as db:
		bundle = McpBundle(org_id=org_id, slug=slug, name=slug.title(), is_active=active)
		db.add(bundle)
		await db.flush()
		for pattern in tools:
			db.add(McpBundleTool(org_id=org_id, bundle_id=bundle.id, tool_pattern=pattern))
		await db.commit()
		return bundle.id


async def attach(org_id, key_id, bundle_id) -> None:
	async with org_scoped_session(org_id) as db:
		db.add(ApiKeyMcpBundle(api_key_id=key_id, bundle_id=bundle_id, org_id=org_id))
		await db.commit()


async def count(org_id, model) -> int:
	async with org_scoped_session(org_id) as db:
		return await db.scalar(select(func.count()).select_from(model))


async def test_resolution_requires_attachment_activity_and_matching_slug(tenants):
	key, other_key = await make_key(tenants), await make_key(tenants)
	bundle = await make_bundle(tenants.a, tools=("github__*", "jira__read"))
	await make_bundle(tenants.a, slug="dormant", active=False)
	await attach(tenants.a, key, bundle)

	async with org_scoped_session(tenants.a) as db:
		assert await load_bundle_patterns(db, tenants.a, key, "readonly") == ("github__*", "jira__read")
		assert await load_bundle_patterns(db, tenants.a, other_key, "readonly") is None  # not attached
		assert await load_bundle_patterns(db, tenants.a, key, "missing") is None
		assert await key_has_bundles(db, tenants.a, key) is True
		assert await key_has_bundles(db, tenants.a, other_key) is False


async def test_inactive_bundles_do_not_resolve(tenants):
	key = await make_key(tenants)
	await attach(tenants.a, key, await make_bundle(tenants.a, slug="dormant", active=False))
	async with org_scoped_session(tenants.a) as db:
		assert await load_bundle_patterns(db, tenants.a, key, "dormant") is None


async def test_other_orgs_cannot_see_resolve_or_forge_bundles(tenants):
	key = await make_key(tenants)
	await attach(tenants.a, key, await make_bundle(tenants.a))
	for model in (McpBundle, McpBundleTool, ApiKeyMcpBundle):
		assert await count(tenants.b, model) == 0
	async with org_scoped_session(tenants.b) as db:
		assert await load_bundle_patterns(db, tenants.a, key, "readonly") is None
		db.add(McpBundle(org_id=tenants.a, slug="forged", name="x"))
		with pytest.raises(DBAPIError):
			await db.flush()


async def test_constraints_reject_bad_slugs_and_duplicates(tenants):
	for slug in ("Upper", "has_underscore", "-lead", "a--b", "x" * 41, ""):
		async with org_scoped_session(tenants.a) as db:
			db.add(McpBundle(org_id=tenants.a, slug=slug, name="x"))
			with pytest.raises(DBAPIError):
				await db.flush()
	await make_bundle(tenants.a, slug="dup")
	async with org_scoped_session(tenants.a) as db:
		db.add(McpBundle(org_id=tenants.a, slug="dup", name="again"))
		with pytest.raises(DBAPIError):
			await db.flush()


async def test_cascades_remove_tools_and_attachments(tenants):
	key = await make_key(tenants)
	bundle = await make_bundle(tenants.a, tools=("a", "b"))
	await attach(tenants.a, key, bundle)
	async with org_scoped_session(tenants.a) as db:
		await db.delete(await db.get(McpBundle, bundle))
		await db.commit()
	assert await count(tenants.a, McpBundleTool) == 0 and await count(tenants.a, ApiKeyMcpBundle) == 0

	bundle = await make_bundle(tenants.a, slug="second")
	await attach(tenants.a, key, bundle)
	async with org_scoped_session(tenants.a) as db:
		await db.delete(await db.get(ApiKey, key))
		await db.commit()
	assert await count(tenants.a, ApiKeyMcpBundle) == 0 and await count(tenants.a, McpBundle) == 1


async def test_admin_api_flow(tenants):
	from httpx import ASGITransport, AsyncClient

	from app.dependencies import get_current_user_from_jwt, get_db
	from app.main import app

	user = tenants.user_a
	key = await make_key(tenants)

	async def fake_user():
		return user

	async def scoped_db():
		async with org_scoped_session(tenants.a) as session:
			yield session

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	app.dependency_overrides[get_db] = scoped_db
	try:
		async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as http:
			created = await http.post("/api/v1/mcp-bundles", json={
				"slug": "support", "name": "Support agent", "tools": ["zendesk__*", "kb__search", "kb__search"]})
			assert created.status_code == 201 and created.json()["tools"] == ["kb__search", "zendesk__*"]
			bundle_id = created.json()["id"]

			assert (await http.post("/api/v1/mcp-bundles", json={"slug": "support", "name": "dup"})).status_code == 409
			for bad in ({"slug": "Bad_Slug", "name": "x"}, {"slug": "ok", "name": ""}, {"slug": "ok", "name": "x", "tools": ["a b"]}):
				assert (await http.post("/api/v1/mcp-bundles", json=bad)).status_code == 422, bad

			attached = await http.put(f"/api/v1/mcp-bundles/{bundle_id}/keys/{key}")
			assert attached.status_code == 200 and attached.json()["api_key_ids"] == [str(key)]
			assert (await http.put(f"/api/v1/mcp-bundles/{bundle_id}/keys/{key}")).status_code == 200  # idempotent
			assert (await http.put(f"/api/v1/mcp-bundles/{bundle_id}/keys/{uuid.uuid4()}")).status_code == 404

			patched = await http.patch(f"/api/v1/mcp-bundles/{bundle_id}", json={"tools": ["kb__*"], "description": "d"})
			assert patched.json()["tools"] == ["kb__*"] and patched.json()["description"] == "d"
			assert (await http.patch(f"/api/v1/mcp-bundles/{bundle_id}", json={})).status_code == 422
			assert (await http.patch(f"/api/v1/mcp-bundles/{bundle_id}", json={"is_active": False})).json()["is_active"] is False

			user.role = "developer"
			assert (await http.post("/api/v1/mcp-bundles", json={"slug": "x", "name": "x"})).status_code == 403
			assert (await http.delete(f"/api/v1/mcp-bundles/{bundle_id}")).status_code == 403
			assert len((await http.get("/api/v1/mcp-bundles")).json()) == 1
			user.role = "admin"

			assert (await http.delete(f"/api/v1/mcp-bundles/{bundle_id}/keys/{key}")).json()["api_key_ids"] == []
			assert (await http.delete(f"/api/v1/mcp-bundles/{uuid.uuid4()}")).status_code == 404
			assert (await http.delete(f"/api/v1/mcp-bundles/{bundle_id}")).status_code == 204
			assert (await http.get("/api/v1/mcp-bundles")).json() == []
	finally:
		app.dependency_overrides.clear()
