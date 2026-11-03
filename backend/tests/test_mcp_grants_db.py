"""Per-tool grants against the real schema: RLS, the admin API, and the gateway reading them back."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import DBAPIError

from app.database import org_scoped_session
from app.models.tool_grant import ToolGrant
from app.services.mcp_grants import GrantRule, load_grants
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


async def test_grants_are_org_scoped_and_forgery_is_rejected(tenants):
	async with org_scoped_session(tenants.a) as db:
		db.add(ToolGrant(org_id=tenants.a, subject_type="role", subject_id="developer", tool_pattern="github__*", effect="allow"))
		await db.commit()

	async with org_scoped_session(tenants.a) as db:
		assert await load_grants(db, tenants.a) == [GrantRule("role", "developer", "github__*", "allow")]
	async with org_scoped_session(tenants.b) as db:
		assert await load_grants(db, tenants.a) == []  # RLS hides org A's rows even when asked by id
		db.add(ToolGrant(org_id=tenants.a, subject_type="role", subject_id="viewer", tool_pattern="*", effect="deny"))
		with pytest.raises(DBAPIError):
			await db.flush()


async def test_database_rejects_unknown_subject_types_and_effects(tenants):
	for bad in ({"subject_type": "agent", "effect": "allow"}, {"subject_type": "role", "effect": "maybe"}):
		async with org_scoped_session(tenants.a) as db:
			db.add(ToolGrant(org_id=tenants.a, subject_id="developer", tool_pattern="*", **bad))
			with pytest.raises(DBAPIError):
				await db.flush()


async def test_admin_api_crud(tenants):
	from httpx import ASGITransport, AsyncClient

	from app.dependencies import get_current_user_from_jwt, get_db
	from app.main import app

	user = tenants.user_a

	async def fake_user():
		return user

	async def scoped_db():
		async with org_scoped_session(tenants.a) as session:
			yield session

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	app.dependency_overrides[get_db] = scoped_db
	body = {"subject_type": "role", "subject_id": "developer", "tool_pattern": "jira__*", "effect": "deny"}
	try:
		async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as http:
			created = await http.post("/api/v1/mcp-grants", json=body)
			assert created.status_code == 201 and created.json()["tool_pattern"] == "jira__*"
			assert (await http.post("/api/v1/mcp-grants", json=body)).status_code == 409

			for bad in (
				{**body, "subject_id": "superuser"},
				{**body, "subject_type": "team", "subject_id": "not-a-uuid"},
				{**body, "tool_pattern": "a b"},
				{**body, "subject_type": "agent"},
				{**body, "effect": "maybe"},
			):
				assert (await http.post("/api/v1/mcp-grants", json=bad)).status_code == 422, bad

			user.role = "developer"
			assert (await http.post("/api/v1/mcp-grants", json={**body, "tool_pattern": "x"})).status_code == 403
			assert (await http.delete(f"/api/v1/mcp-grants/{created.json()['id']}")).status_code == 403
			assert len((await http.get("/api/v1/mcp-grants")).json()) == 1  # reading is allowed to members
			user.role = "admin"

			assert (await http.delete(f"/api/v1/mcp-grants/{uuid.uuid4()}")).status_code == 404
			assert (await http.delete(f"/api/v1/mcp-grants/{created.json()['id']}")).status_code == 204
			assert (await http.get("/api/v1/mcp-grants")).json() == []
	finally:
		app.dependency_overrides.clear()
