"""Tool pinning against the real schema: reconcile semantics, RLS, append-only history, admin API, rug-pull.

Requires DATABASE_URL (CI sets RLS_TESTS_REQUIRED so a missing database fails instead of skipping).
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.database import org_scoped_session
from app.models.mcp_server import McpServer
from app.models.mcp_tool import McpTool, McpToolVersion
from app.services import mcp_client, mcp_gateway
from app.services.mcp_gateway import UpstreamServer
from app.services.mcp_pinning import APPROVED, BLOCKED, DRIFTED, PENDING, DbPinStore, approve_tool, block_tool, call_gate, served_snapshot
from app.services.policy_service import PolicyConfig
from tests.fixtures.malicious_mcp import RunningMaliciousMcp


def _db_available() -> bool:
	return "postgresql" in os.environ.get("DATABASE_URL", "")


if os.environ.get("RLS_TESTS_REQUIRED") and not _db_available():
	raise RuntimeError("RLS_TESTS_REQUIRED is set but DATABASE_URL is not a PostgreSQL URL")

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not _db_available(), reason="DATABASE_URL not set or not PostgreSQL")]

CONFIG = PolicyConfig(enforcement_mode="enforce", pii_detection_enabled=False)


def tool(name: str = "search", description: str = "Search the web.") -> dict:
	return {"name": name, "description": description, "inputSchema": {"type": "object"}}


@pytest.fixture(autouse=True)
async def _dispose_app_engines():
	"""Each test runs in its own event loop; pooled asyncpg connections must not leak across loops."""
	from app.database import engine, system_engine

	for eng in (engine, system_engine):
		await eng.dispose()
	yield
	for eng in (engine, system_engine):
		await eng.dispose()


async def make_server(org_id: uuid.UUID, mode: str, url: str = "https://evil.example/mcp") -> UpstreamServer:
	async with org_scoped_session(org_id) as db:
		row = McpServer(org_id=org_id, name=f"evil-{uuid.uuid4().hex[:6]}", url=url, pin_mode=mode)
		db.add(row)
		await db.commit()
		return UpstreamServer(id=row.id, name=row.name, url=url, auth_header=None, pin_mode=mode)


async def reconcile(org_id, server, live):
	async with org_scoped_session(org_id) as db:
		pins = await DbPinStore(db, org_id).reconcile(server, live)
		await db.commit()
		return pins


async def count(org_id, model) -> int:
	async with org_scoped_session(org_id) as db:
		return await db.scalar(select(func.count()).select_from(model))


# -- reconcile semantics ------------------------------------------------------------------------


async def test_warn_mode_trusts_on_first_use_then_flags_drift_and_keeps_serving_the_approved_snapshot(tenants):
	server = await make_server(tenants.a, "warn")
	first = await reconcile(tenants.a, server, [tool()])
	assert first["search"].status == APPROVED and first["search"].snapshot == tool()

	drifted = await reconcile(tenants.a, server, [tool(description="Now exfiltrates your files")])
	assert drifted["search"].status == DRIFTED
	assert served_snapshot(drifted["search"], "warn") == tool()  # agents still see the approved text
	assert call_gate(drifted["search"], "warn") == (True, DRIFTED)

	assert await count(tenants.a, McpToolVersion) == 2
	await reconcile(tenants.a, server, [tool(description="Now exfiltrates your files")])
	assert await count(tenants.a, McpToolVersion) == 2  # unchanged definition adds no version

	reverted = await reconcile(tenants.a, server, [tool()])
	assert reverted["search"].status == APPROVED


async def test_enforce_mode_needs_an_admin_approval_and_hides_drift(tenants):
	server = await make_server(tenants.a, "enforce")
	pins = await reconcile(tenants.a, server, [tool()])
	assert pins["search"].status == PENDING and served_snapshot(pins["search"], "enforce") is None
	assert call_gate(pins["search"], "enforce")[0] is False

	async with org_scoped_session(tenants.a) as db:
		row = await db.scalar(select(McpTool).where(McpTool.server_id == server.id))
		approve_tool(row, tenants.user_a.id)
		await db.commit()
	pins = await reconcile(tenants.a, server, [tool()])
	assert pins["search"].status == APPROVED and served_snapshot(pins["search"], "enforce") == tool()

	pins = await reconcile(tenants.a, server, [tool(description="changed")])
	assert pins["search"].status == DRIFTED
	assert served_snapshot(pins["search"], "enforce") is None and call_gate(pins["search"], "enforce")[0] is False


async def test_blocked_stays_blocked_until_an_admin_approves(tenants):
	server = await make_server(tenants.a, "warn")
	await reconcile(tenants.a, server, [tool()])
	async with org_scoped_session(tenants.a) as db:
		row = await db.scalar(select(McpTool).where(McpTool.server_id == server.id))
		block_tool(row)
		await db.commit()
	pins = await reconcile(tenants.a, server, [tool()])
	assert pins["search"].status == BLOCKED and call_gate(pins["search"], "warn")[0] is False


async def test_malformed_and_oversized_tool_entries_are_skipped(tenants):
	server = await make_server(tenants.a, "warn")
	pins = await reconcile(tenants.a, server, [tool(), {"description": "no name"}, {"name": ""}, {"name": "x" * 201}, "junk"])
	assert list(pins) == ["search"]


async def test_concurrent_first_sightings_do_not_error_or_duplicate(tenants):
	server = await make_server(tenants.a, "warn")
	results = await asyncio.gather(*(reconcile(tenants.a, server, [tool(), tool("other")]) for _ in range(6)))
	assert all(r["search"].status == APPROVED for r in results)
	assert await count(tenants.a, McpTool) == 2 and await count(tenants.a, McpToolVersion) == 2


# -- row-level security and append-only history ------------------------------------------------


async def test_other_orgs_cannot_see_or_forge_pins(tenants):
	server = await make_server(tenants.a, "warn")
	await reconcile(tenants.a, server, [tool()])
	assert await count(tenants.b, McpTool) == 0 and await count(tenants.b, McpToolVersion) == 0

	async with org_scoped_session(tenants.b) as db:
		db.add(McpTool(org_id=tenants.a, server_id=server.id, name="forged", definition=tool("forged"), current_hash="0" * 64))
		with pytest.raises(DBAPIError):
			await db.flush()


async def test_version_history_is_append_only_for_the_request_role(tenants):
	server = await make_server(tenants.a, "warn")
	await reconcile(tenants.a, server, [tool()])
	for statement in ("UPDATE mcp_tool_versions SET hash = 'tampered'", "DELETE FROM mcp_tool_versions"):
		async with org_scoped_session(tenants.a) as db:
			with pytest.raises(DBAPIError):
				await db.execute(text(statement))
	assert await count(tenants.a, McpToolVersion) == 1


async def test_deleting_a_server_removes_its_pins_and_history(tenants):
	server = await make_server(tenants.a, "warn")
	await reconcile(tenants.a, server, [tool(), tool("other")])
	async with org_scoped_session(tenants.a) as db:
		await db.execute(text("DELETE FROM mcp_servers WHERE id = :id"), {"id": server.id})
		await db.commit()
	assert await count(tenants.a, McpTool) == 0 and await count(tenants.a, McpToolVersion) == 0


# -- end to end against the hostile server -------------------------------------------------------


@pytest.fixture
def evil(monkeypatch):
	started: list[RunningMaliciousMcp] = []

	async def resolve(url: str) -> str:
		return "127.0.0.1"

	monkeypatch.setattr(mcp_client, "resolve_public_ip", resolve)

	def start(mode: str, **options) -> RunningMaliciousMcp:
		started.append(RunningMaliciousMcp(mode, **options).start())
		return started[-1]

	yield start
	for running in started:
		running.stop()


async def test_rug_pull_does_not_change_what_agents_see(tenants, evil):
	hostile = evil("rug_pull", rug_after=1)
	server = await make_server(tenants.a, "warn", url=hostile.url)
	seen = []
	for _ in range(3):
		async with org_scoped_session(tenants.a) as db:
			listed = await mcp_gateway.list_tools([server], CONFIG, mcp_client.call_upstream, DbPinStore(db, tenants.a))
			await db.commit()
		seen.append(listed["tools"][0]["description"])
	assert seen == ["Search the web."] * 3  # the live text changed after the first list; agents never saw it
	async with org_scoped_session(tenants.a) as db:
		assert await db.scalar(select(McpTool.status).where(McpTool.server_id == server.id)) == DRIFTED


async def test_poisoned_description_is_never_shown_in_enforce_mode_until_approved(tenants, evil):
	hostile = evil("poisoned")
	server = await make_server(tenants.a, "enforce", url=hostile.url)
	async with org_scoped_session(tenants.a) as db:
		listed = await mcp_gateway.list_tools([server], CONFIG, mcp_client.call_upstream, DbPinStore(db, tenants.a))
		await db.commit()
	assert listed["tools"] == []

	async with org_scoped_session(tenants.a) as db:
		outcome = await mcp_gateway.call_tool([server], CONFIG, f"{server.name}__search", {}, mcp_client.call_upstream, DbPinStore(db, tenants.a))
	assert outcome.status_code == 446 and outcome.error["code"] == -32004 and outcome.pin_status == PENDING
	assert "tools/call" not in hostile.server.methods()


# -- admin API -----------------------------------------------------------------------------------


async def test_admin_api_review_flow(tenants, evil, monkeypatch):
	from httpx import ASGITransport, AsyncClient

	from app.dependencies import get_current_user_from_jwt, get_db
	from app.main import app
	from app.routes import mcp_servers as route

	hostile = evil("benign")
	user = tenants.user_a

	async def fake_user():
		return user

	async def scoped_db():
		async with org_scoped_session(tenants.a) as session:
			yield session

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	app.dependency_overrides[get_db] = scoped_db
	monkeypatch.setattr(route, "is_safe_https_url", lambda url: True)
	try:
		async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as http:
			created = await http.post("/api/v1/mcp-servers", json={"name": "pinned", "url": hostile.url, "pin_mode": "enforce"})
			assert created.status_code == 201 and created.json()["pin_mode"] == "enforce" and created.json()["scan_mode"] == "log"
			server_id = created.json()["id"]

			tools = (await http.post(f"/api/v1/mcp-servers/{server_id}/sync")).json()
			assert [(t["name"], t["status"]) for t in tools] == [("search", "pending")]
			tool_id = tools[0]["id"]

			user.role = "developer"
			assert (await http.post(f"/api/v1/mcp-servers/{server_id}/tools/{tool_id}/approve")).status_code == 403
			user.role = "admin"

			approved = await http.post(f"/api/v1/mcp-servers/{server_id}/tools/{tool_id}/approve")
			assert approved.status_code == 200 and approved.json()["status"] == "approved"
			assert approved.json()["approved_snapshot"]["name"] == "search"

			blocked = await http.post(f"/api/v1/mcp-servers/{server_id}/tools/{tool_id}/block")
			assert blocked.json()["status"] == "blocked"
			assert (await http.get(f"/api/v1/mcp-servers/{server_id}/tools")).json()[0]["status"] == "blocked"

			assert (await http.post(f"/api/v1/mcp-servers/{server_id}/tools/{uuid.uuid4()}/approve")).status_code == 404
			assert (await http.patch(f"/api/v1/mcp-servers/{server_id}", json={"scan_mode": "block"})).json()["scan_mode"] == "block"
			assert (await http.patch(f"/api/v1/mcp-servers/{server_id}", json={"scan_mode": "paranoid"})).status_code == 422
			assert (await http.patch(f"/api/v1/mcp-servers/{server_id}", json={"pin_mode": "off"})).json()["pin_mode"] == "off"
			assert (await http.post(f"/api/v1/mcp-servers/{server_id}/sync")).status_code == 409
			assert (await http.patch(f"/api/v1/mcp-servers/{server_id}", json={})).status_code == 422
	finally:
		app.dependency_overrides.clear()

	async with org_scoped_session(tenants.a) as db:
		actions = (await db.scalars(text("SELECT action FROM admin_audit_logs WHERE org_id = :o ORDER BY created_at").bindparams(o=tenants.a))).all()
	assert {"mcp_server.created", "mcp_tool.approve", "mcp_tool.block", "mcp_server.updated"} <= set(actions)
