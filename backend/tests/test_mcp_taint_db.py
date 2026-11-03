"""Trust rules against the real schema: RLS, constraints, admin API."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import DBAPIError

from app.database import org_scoped_session
from app.models.tool_trust_rule import ToolTrustRule
from app.services.mcp_taint import TrustRules, load_trust_rules
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


async def test_rules_are_org_scoped_and_forgery_is_rejected(tenants):
	async with org_scoped_session(tenants.a) as db:
		db.add_all([
			ToolTrustRule(org_id=tenants.a, tool_pattern="kb__*", rule="trusted_output"),
			ToolTrustRule(org_id=tenants.a, tool_pattern="mail__send", rule="sink"),
		])
		await db.commit()
	async with org_scoped_session(tenants.a) as db:
		assert await load_trust_rules(db, tenants.a) == TrustRules(trusted_output=("kb__*",), sinks=("mail__send",))
	async with org_scoped_session(tenants.b) as db:
		assert await load_trust_rules(db, tenants.a) == TrustRules()
		db.add(ToolTrustRule(org_id=tenants.a, tool_pattern="x", rule="sink"))
		with pytest.raises(DBAPIError):
			await db.flush()


async def test_database_rejects_unknown_rule_kinds_and_duplicates(tenants):
	async with org_scoped_session(tenants.a) as db:
		db.add(ToolTrustRule(org_id=tenants.a, tool_pattern="x", rule="trusted"))
		with pytest.raises(DBAPIError):
			await db.flush()
	for _ in range(2):
		async with org_scoped_session(tenants.a) as db:
			db.add(ToolTrustRule(org_id=tenants.a, tool_pattern="dup", rule="sink"))
			try:
				await db.commit()
			except DBAPIError:
				return  # the second insert violated the unique constraint
	pytest.fail("duplicate rule was accepted")


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
	body = {"tool_pattern": "mail__send*", "rule": "sink"}
	try:
		async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as http:
			created = await http.post("/api/v1/mcp-trust-rules", json=body)
			assert created.status_code == 201 and created.json()["rule"] == "sink"
			assert (await http.post("/api/v1/mcp-trust-rules", json=body)).status_code == 409
			for bad in ({**body, "rule": "trusted"}, {**body, "tool_pattern": "a b"}, {"rule": "sink"}):
				assert (await http.post("/api/v1/mcp-trust-rules", json=bad)).status_code == 422

			user.role = "developer"
			assert (await http.post("/api/v1/mcp-trust-rules", json={**body, "tool_pattern": "x"})).status_code == 403
			assert (await http.delete(f"/api/v1/mcp-trust-rules/{created.json()['id']}")).status_code == 403
			assert len((await http.get("/api/v1/mcp-trust-rules")).json()) == 1
			user.role = "admin"

			assert (await http.delete(f"/api/v1/mcp-trust-rules/{uuid.uuid4()}")).status_code == 404
			assert (await http.delete(f"/api/v1/mcp-trust-rules/{created.json()['id']}")).status_code == 204
			assert (await http.get("/api/v1/mcp-trust-rules")).json() == []
	finally:
		app.dependency_overrides.clear()
