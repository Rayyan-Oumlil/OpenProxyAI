"""HTTP surface of the MCP gateway (POST /v1/mcp) and its admin API (/api/v1/mcp-servers)."""

import json
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from app import database
from app.dependencies import (
	get_current_user_from_api_key,
	get_current_user_from_jwt,
	get_db,
	get_redis,
)
from app.main import app
from app.routes import mcp as mcp_route
from app.routes import mcp_servers as mcp_servers_route
from app.services import mcp_audit
from app.services.policy_service import PolicyConfig

ORG = uuid.uuid4()
USER = SimpleNamespace(id=uuid.uuid4(), org_id=ORG, email="dev@acme.io", role="admin", is_active=True)
API_KEY = SimpleNamespace(id=uuid.uuid4(), org_id=ORG, team_id=None)
SERVER = SimpleNamespace(id=uuid.uuid4(), org_id=ORG, name="github", url="https://gh.example.com/mcp",
                         auth_header_encrypted=None, is_active=True, created_at=datetime(2026, 9, 30))


class _Rows:
	def __init__(self, rows):
		self._rows = rows

	def all(self):
		return self._rows


class FakeDB:
	def __init__(self, servers=None):
		self.servers = list(servers if servers is not None else [SERVER])
		self.added: list = []
		self.deleted: list = []
		self.info: dict = {}

	async def scalars(self, *args, **kwargs):
		return _Rows(self.servers)

	async def get(self, model, key):
		return next((s for s in self.servers if s.id == key), None)

	async def execute(self, *args, **kwargs):
		return None

	def add(self, obj):
		self.added.append(obj)

	async def delete(self, obj):
		self.deleted.append(obj)

	async def flush(self):
		for obj in self.added:
			if getattr(obj, "id", None) is None:
				obj.id = uuid.uuid4()
			if getattr(obj, "created_at", None) is None:
				obj.created_at = datetime(2026, 9, 30)
			if getattr(obj, "is_active", None) is None:
				obj.is_active = True

	async def commit(self):
		await self.flush()

	async def refresh(self, obj):
		return None


@pytest.fixture
def gateway(monkeypatch):
	"""Authenticated gateway with one upstream server and a recording audit writer."""
	db = FakeDB()
	audits: list[dict] = []
	upstream_calls: list[tuple] = []

	async def fake_auth():
		return USER, API_KEY

	async def fake_db():
		yield db

	async def fake_redis():
		return None

	async def fake_policy(org_id, db_, redis):
		return PolicyConfig(enforcement_mode="enforce", pii_detection_enabled=False, mcp_blocked_tools=["*__delete_*"])

	async def fake_upstream(url, auth, method, params):
		upstream_calls.append((url, method, params))
		if method == "tools/list":
			return {"tools": [{"name": "search", "inputSchema": {"type": "object"}}, {"name": "delete_repo", "inputSchema": {"type": "object"}}]}
		return {"content": [{"type": "text", "text": "ok"}], "isError": False}

	async def fake_record(**kwargs):
		audits.append(kwargs)

	app.dependency_overrides[get_current_user_from_api_key] = fake_auth
	app.dependency_overrides[get_db] = fake_db
	app.dependency_overrides[get_redis] = fake_redis
	monkeypatch.setattr(mcp_route.policy_store, "load", fake_policy)
	monkeypatch.setattr(mcp_route, "call_upstream", fake_upstream)
	monkeypatch.setattr(mcp_route, "record_tool_call", fake_record)
	return SimpleNamespace(db=db, audits=audits, upstream_calls=upstream_calls)


def rpc(client, method, params=None, id_=1):
	body = {"jsonrpc": "2.0", "method": method}
	if id_ is not None:
		body["id"] = id_
	if params is not None:
		body["params"] = params
	return client.post("/v1/mcp", json=body, headers={"Authorization": "Bearer opai_test"})


# ── POST /v1/mcp ──────────────────────────────────────────────────────────────


def test_gateway_requires_an_api_key(client):
	response = client.post("/v1/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
	assert response.status_code == 401


def test_initialize_negotiates_and_issues_a_session(client, gateway):
	response = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
	assert response.status_code == 200
	result = response.json()["result"]
	assert result["protocolVersion"] == "2025-06-18"
	assert result["capabilities"] == {"tools": {"listChanged": False}}
	assert result["serverInfo"]["name"] == "OpenProxyAI MCP Gateway"
	assert response.headers["mcp-session-id"]


def test_unknown_protocol_version_gets_the_latest(client, gateway):
	response = rpc(client, "initialize", {"protocolVersion": "1999-01-01", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
	assert response.json()["result"]["protocolVersion"] == "2025-11-25"


def test_notifications_are_accepted_without_a_body(client, gateway):
	response = rpc(client, "notifications/initialized", id_=None)
	assert response.status_code == 202 and response.content == b""


def test_ping(client, gateway):
	assert rpc(client, "ping").json() == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_tools_list_is_namespaced_and_filtered(client, gateway):
	tools = rpc(client, "tools/list").json()["result"]["tools"]
	assert [t["name"] for t in tools] == ["github__search"]


def test_tools_call_forwards_and_is_audited(client, gateway):
	response = rpc(client, "tools/call", {"name": "github__search", "arguments": {"q": "rls"}}, id_="abc")
	assert response.json() == {"jsonrpc": "2.0", "id": "abc", "result": {"content": [{"type": "text", "text": "ok"}], "isError": False}}
	assert gateway.upstream_calls[-1] == (SERVER.url, "tools/call", {"name": "search", "arguments": {"q": "rls"}})
	(audit,) = gateway.audits
	assert audit["org_id"] == ORG and audit["api_key_id"] == API_KEY.id and audit["user_id"] == USER.id
	assert audit["outcome"].status_code == 200 and audit["outcome"].tool == "github__search"


def test_blocked_tools_call_is_a_json_rpc_error_and_still_audited(client, gateway):
	response = rpc(client, "tools/call", {"name": "github__delete_repo", "arguments": {}})
	assert response.status_code == 200
	error = response.json()["error"]
	assert error["code"] == -32001 and error["data"]["reason_code"] == "tool_blocked"
	assert [c for c in gateway.upstream_calls if c[1] == "tools/call"] == []
	assert gateway.audits[0]["outcome"].status_code == 446


def test_unknown_method(client, gateway):
	assert rpc(client, "resources/list").json()["error"]["code"] == -32601


def test_malformed_json_is_a_parse_error(client, gateway):
	response = client.post("/v1/mcp", content=b"{not json", headers={"Authorization": "Bearer opai_test", "Content-Type": "application/json"})
	assert response.status_code == 400 and response.json()["error"]["code"] == -32700


@pytest.mark.parametrize("body", [{"id": 1, "method": "ping"}, [{"jsonrpc": "2.0", "id": 1, "method": "ping"}], {"jsonrpc": "2.0", "id": 1}])
def test_invalid_requests(client, gateway, body):
	response = client.post("/v1/mcp", json=body, headers={"Authorization": "Bearer opai_test"})
	assert response.status_code == 400 and response.json()["error"]["code"] == -32600


def test_server_initiated_streams_are_not_offered(client, gateway):
	assert client.get("/v1/mcp", headers={"Authorization": "Bearer opai_test"}).status_code == 405


# ── audit writer ─────────────────────────────────────────────────────────────


async def test_audit_row_is_org_scoped_and_describes_the_call(monkeypatch):
	from app.services.mcp_gateway import ToolCallOutcome
	from app.services.policy_service import PolicyDecision

	log: list = []

	class Session:
		info: dict = {}

		async def __aenter__(self):
			return self

		async def __aexit__(self, *exc):
			return False

		async def execute(self, statement, params=None):
			log.append(("org", (params or {}).get("org_id")))

		def add(self, row):
			log.append(("row", row))

		async def commit(self):
			log.append(("commit",))

	monkeypatch.setattr(database, "AsyncSessionLocal", Session)
	outcome = ToolCallOutcome(tool="github__delete_repo", server="github", status_code=446,
	                          decision=PolicyDecision(allowed=False, action="block", reason_code="tool_blocked"),
	                          error={"code": -32001, "message": "blocked"})
	await mcp_audit.record_tool_call(org_id=ORG, user_id=USER.id, api_key_id=API_KEY.id, outcome=outcome, latency_ms=12)

	assert log[0] == ("org", str(ORG))
	row = log[1][1]
	assert (row.org_id, row.model, row.provider, row.status_code, row.latency_ms) == (ORG, "github__delete_repo", "mcp:github", 446, 12)
	assert row.request_metadata["type"] == "mcp_tool_call"
	assert row.request_metadata["policy"]["reason_code"] == "tool_blocked"
	assert row.error_message == "blocked"
	assert log[-1] == ("commit",)


# ── /api/v1/mcp-servers ─────────────────────────────────────────────────────


@pytest.fixture
def admin_api(monkeypatch):
	db = FakeDB()
	user = SimpleNamespace(**USER.__dict__)
	audit_actions: list[str] = []

	async def fake_user():
		return user

	async def fake_db():
		yield db

	async def fake_log_admin_action(db_, **kwargs):
		audit_actions.append(kwargs["action"])

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	app.dependency_overrides[get_db] = fake_db
	monkeypatch.setattr(mcp_servers_route, "log_admin_action", fake_log_admin_action)
	monkeypatch.setattr(mcp_servers_route, "is_safe_https_url", lambda url: url.startswith("https://"))
	monkeypatch.setattr(mcp_servers_route, "encrypt", lambda s: f"enc({s})")
	return SimpleNamespace(db=db, user=user, audit_actions=audit_actions)


AUTH = {"Authorization": "Bearer jwt"}


def test_list_never_exposes_the_upstream_secret(client, admin_api):
	admin_api.db.servers[0] = SimpleNamespace(**{**SERVER.__dict__, "auth_header_encrypted": "enc(x)"})
	body = client.get("/api/v1/mcp-servers", headers=AUTH).json()
	assert body[0]["name"] == "github" and body[0]["has_auth"] is True
	assert "auth_header" not in body[0] and "auth_header_encrypted" not in body[0]


def test_create_requires_admin(client, admin_api):
	admin_api.user.role = "developer"
	response = client.post("/api/v1/mcp-servers", json={"name": "jira", "url": "https://jira.example.com/mcp"}, headers=AUTH)
	assert response.status_code == 403


def test_create_rejects_unsafe_urls(client, admin_api):
	response = client.post("/api/v1/mcp-servers", json={"name": "jira", "url": "http://10.0.0.5/mcp"}, headers=AUTH)
	assert response.status_code == 400


@pytest.mark.parametrize("name", ["Jira", "ji__ra", "", "x" * 41, "a b"])
def test_create_rejects_names_that_break_namespacing(client, admin_api, name):
	response = client.post("/api/v1/mcp-servers", json={"name": name, "url": "https://jira.example.com/mcp"}, headers=AUTH)
	assert response.status_code == 422


def test_create_encrypts_the_secret_and_audits(client, admin_api):
	response = client.post(
		"/api/v1/mcp-servers",
		json={"name": "jira", "url": "https://jira.example.com/mcp", "auth_header": "Bearer s3cret"},
		headers=AUTH,
	)
	assert response.status_code == 201, response.text
	assert response.json()["has_auth"] is True and "s3cret" not in response.text
	created = admin_api.db.added[0]
	assert created.org_id == ORG and created.auth_header_encrypted == "enc(Bearer s3cret)"
	assert admin_api.audit_actions == ["mcp_server.created"]


def test_toggle_and_delete(client, admin_api):
	server_id = SERVER.id
	patched = client.patch(f"/api/v1/mcp-servers/{server_id}", json={"is_active": False}, headers=AUTH)
	assert patched.status_code == 200 and patched.json()["is_active"] is False
	assert client.delete(f"/api/v1/mcp-servers/{server_id}", headers=AUTH).status_code == 204
	assert admin_api.audit_actions == ["mcp_server.updated", "mcp_server.deleted"]


def test_delete_missing_server_is_404(client, admin_api):
	assert client.delete(f"/api/v1/mcp-servers/{uuid.uuid4()}", headers=AUTH).status_code == 404


# ── end to end: route → gateway → policy → real client → simulated upstream over HTTP ──


def test_end_to_end_through_the_real_client(client, gateway, monkeypatch):
	import httpx

	from app.services import mcp_client
	from tests.test_mcp_client import FakeUpstream

	upstream = FakeUpstream(sse=True)
	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
	monkeypatch.setattr(mcp_client, "is_safe_https_url", lambda url: True)
	monkeypatch.setattr(mcp_route, "call_upstream", mcp_client.call_upstream)

	response = rpc(client, "tools/call", {"name": "github__search", "arguments": {"q": "rls"}})
	assert response.json()["result"] == {"echo": "tools/call", "params": {"name": "search", "arguments": {"q": "rls"}}}
	methods = [json.loads(r.content)["method"] for r in upstream.requests]
	assert methods == ["initialize", "notifications/initialized", "tools/call"]
	assert gateway.audits[0]["outcome"].status_code == 200
