# ruff: noqa: F811  (the `gateway` fixture is imported from test_mcp_routes and then used as a test argument)
"""The gateway never hands the caller's credentials to an upstream MCP server (no token pass-through).

An upstream sees only the credential an admin stored for that one server (or none). Everything the
agent sent us (its gateway key, cookies, session id, forwarding headers) stays on our side.
These tests run the real HTTP route and the real upstream client against a recording fake server.
"""

import json
import uuid
from datetime import datetime
from types import SimpleNamespace

import httpx

from app.routes import mcp as mcp_route
from app.services import mcp_client
from app.services.crypto_service import encrypt
from tests.test_mcp_routes import ORG, gateway, rpc  # noqa: F401

CALLER_KEY = "opai_CALLER_SECRET_123"
FORWARDED_FOR = "203.0.113.9"
STORED_AUTH = "Bearer stored-for-this-server-only"
UPSTREAM_SESSION = "upstream-issued-session"


def _caller_headers(client) -> dict[str, str]:
	"""Everything an agent might send, including a real gateway session (an unknown one is refused with 404)."""
	init = rpc(client, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
	return {
		"Authorization": f"Bearer {CALLER_KEY}",
		"X-API-Key": CALLER_KEY,
		"Proxy-Authorization": f"Basic {CALLER_KEY}",
		"Cookie": f"session={CALLER_KEY}",
		"Mcp-Session-Id": init.headers["mcp-session-id"],
		"X-Forwarded-For": FORWARDED_FOR,
	}


def _server(name: str, auth: str | None):
	return SimpleNamespace(
		id=uuid.uuid4(), org_id=ORG, name=name, url=f"https://{name}.example.com/mcp",
		auth_header_encrypted=encrypt(auth) if auth else None,
		is_active=True, pin_mode="off", scan_mode="off", created_at=datetime(2026, 9, 30),
	)


def _record_upstream(monkeypatch) -> list[httpx.Request]:
	seen: list[httpx.Request] = []

	def fake(request: httpx.Request) -> httpx.Response:
		seen.append(request)
		if request.method == "DELETE":
			return httpx.Response(204)
		body = json.loads(request.content)
		if "id" not in body:
			return httpx.Response(202)
		if body["method"] == "initialize":
			result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": "f", "version": "1"}}
			return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result}, headers={"Mcp-Session-Id": UPSTREAM_SESSION})
		if body["method"] == "tools/list":
			result = {"tools": [{"name": "search", "inputSchema": {"type": "object"}}]}
		else:
			result = {"content": [{"type": "text", "text": "ok"}], "isError": False}
		return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

	async def public(url: str) -> str:
		return "93.184.216.34"

	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
	monkeypatch.setattr(mcp_client, "resolve_public_ip", public)
	monkeypatch.setattr(mcp_route, "call_upstream", mcp_client.call_upstream)  # the real client, not the route test's stub
	return seen


def _caller_values_seen(requests: list[httpx.Request], caller: dict[str, str]) -> list[tuple[str, str]]:
	needles = (CALLER_KEY, caller["Mcp-Session-Id"], FORWARDED_FOR)
	leaks = []
	for request in requests:
		for name, value in request.headers.items():
			if any(needle in value for needle in needles):
				leaks.append((name, value))
	return leaks


def test_a_server_with_its_own_credential_gets_only_that_credential(client, gateway, monkeypatch):
	gateway.db.servers = [_server("github", STORED_AUTH)]
	seen = _record_upstream(monkeypatch)
	caller = _caller_headers(client)
	response = rpc(client, "tools/call", {"name": "github__search", "arguments": {}}, headers=caller)
	assert response.json()["result"]["isError"] is False
	assert seen, "the upstream was never called"
	assert _caller_values_seen(seen, caller) == []
	assert {r.headers.get("authorization") for r in seen} == {STORED_AUTH}


def test_a_server_without_a_credential_receives_no_authorization_at_all(client, gateway, monkeypatch):
	gateway.db.servers = [_server("public", None)]
	seen = _record_upstream(monkeypatch)
	caller = _caller_headers(client)
	rpc(client, "tools/call", {"name": "public__search", "arguments": {}}, headers=caller)
	assert seen
	assert _caller_values_seen(seen, caller) == []
	assert all("authorization" not in r.headers and "proxy-authorization" not in r.headers for r in seen)
	assert all("cookie" not in r.headers and "x-api-key" not in r.headers for r in seen)


def test_the_caller_session_id_is_not_the_upstream_session(client, gateway, monkeypatch):
	gateway.db.servers = [_server("github", STORED_AUTH)]
	seen = _record_upstream(monkeypatch)
	caller = _caller_headers(client)
	rpc(client, "tools/call", {"name": "github__search", "arguments": {}}, headers=caller)
	sessions = {r.headers.get("mcp-session-id") for r in seen if "mcp-session-id" in r.headers}
	assert sessions == {UPSTREAM_SESSION}


def test_each_server_gets_its_own_credential_never_another_servers(client, gateway, monkeypatch):
	gateway.db.servers = [_server("alpha", "Bearer alpha-secret"), _server("beta", "Bearer beta-secret")]
	seen = _record_upstream(monkeypatch)
	caller = _caller_headers(client)
	rpc(client, "tools/list", headers=caller)
	by_host: dict[str, set[str | None]] = {}
	for request in seen:
		by_host.setdefault(request.headers["host"], set()).add(request.headers.get("authorization"))
	assert by_host == {"alpha.example.com": {"Bearer alpha-secret"}, "beta.example.com": {"Bearer beta-secret"}}


def test_tools_list_also_keeps_the_callers_credentials_out(client, gateway, monkeypatch):
	gateway.db.servers = [_server("github", STORED_AUTH)]
	seen = _record_upstream(monkeypatch)
	caller = _caller_headers(client)
	rpc(client, "tools/list", headers=caller)
	assert seen
	assert _caller_values_seen(seen, caller) == []
