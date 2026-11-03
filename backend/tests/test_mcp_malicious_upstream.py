"""The gateway against a hostile upstream MCP server (tests/fixtures/malicious_mcp.py).

Real HTTP, real client, real gateway code: only DNS resolution is stubbed (the fixture listens on
127.0.0.1, which the SSRF guard would otherwise refuse). Tests marked xfail(strict) pin behaviour that
later Phase 1 PRs must deliver; they flip to failures the moment the feature lands, forcing the marker off.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest

from app.dependencies import get_current_user_from_api_key, get_db, get_redis
from app.main import app
from app.routes import mcp as mcp_route
from app.services import mcp_client, mcp_gateway
from app.services.mcp_gateway import UpstreamServer
from app.services.policy_service import PolicyConfig
from app.utils import ssrf
from tests.conftest import FakeRedis
from tests.fixtures.malicious_mcp import INJECTION, METADATA_URL, POISONED_DESCRIPTION, RebindingResolver, RunningMaliciousMcp
from tests.test_mcp_routes import API_KEY, ORG, USER, FakeDB

CONFIG = PolicyConfig(enforcement_mode="enforce", pii_detection_enabled=False)


@pytest.fixture
def hostile(monkeypatch):
	"""Start a hostile server in the given mode; DNS for 127.0.0.1 is stubbed past the SSRF guard."""
	started: list[RunningMaliciousMcp] = []

	async def resolve(url: str) -> str:
		return "127.0.0.1"

	monkeypatch.setattr(mcp_client, "resolve_public_ip", resolve)

	def start(mode: str, **options) -> RunningMaliciousMcp:
		running = RunningMaliciousMcp(mode, **options).start()
		started.append(running)
		return running

	yield start
	for running in started:
		running.stop()


def _server(running: RunningMaliciousMcp, name: str = "evil", auth: str | None = None) -> UpstreamServer:
	return UpstreamServer(name=name, url=running.url, auth_header=auth)


# ── transport ────────────────────────────────────────────────────────────────


async def test_control_case_benign_server_works(hostile):
	evil = hostile("benign")
	result = await mcp_client.call_upstream(evil.url, None, "tools/call", {"name": "search", "arguments": {}})
	assert result["content"][0]["text"] == "ok"
	assert evil.server.methods() == ["initialize", "notifications/initialized", "tools/call", "DELETE"]


async def test_50mb_body_is_cut_off_quickly(hostile, monkeypatch):
	evil = hostile("huge_body")
	started = time.monotonic()
	with pytest.raises(mcp_client.McpUpstreamError, match="too large"):
		await mcp_client.call_upstream(evil.url, None, "tools/call", {"name": "search", "arguments": {}})
	assert time.monotonic() - started < 10


async def test_one_byte_drip_hits_the_deadline_and_still_closes_the_session(hostile, monkeypatch):
	monkeypatch.setattr(mcp_client, "TOTAL_TIMEOUT_SECONDS", 1.0)
	evil = hostile("drip", drip_interval=0.1)
	with pytest.raises(mcp_client.McpUpstreamError, match="timed out"):
		await asyncio.wait_for(mcp_client.call_upstream(evil.url, None, "tools/call", {"name": "search", "arguments": {}}), timeout=10)
	assert evil.server.methods()[-1] == "DELETE"


async def test_redirect_to_the_metadata_service_is_not_followed(hostile):
	evil = hostile("redirect")
	with pytest.raises(mcp_client.McpUpstreamError, match="redirect"):
		await mcp_client.call_upstream(evil.url, None, "tools/list", {})
	assert len(evil.server.requests) == 1  # one request, no follow-up, nothing sent to METADATA_URL
	assert METADATA_URL.startswith("https://169.254.169.254")


async def test_dns_rebinding_cannot_redirect_the_connection(monkeypatch):
	resolver = RebindingResolver()  # public on the first lookup, 127.0.0.1 afterwards
	monkeypatch.setattr(ssrf.socket, "getaddrinfo", resolver)
	seen: list[str] = []

	def fake(request: httpx.Request) -> httpx.Response:
		seen.append(request.url.host)
		body = json.loads(request.content) if request.content else {}
		if "id" not in body:
			return httpx.Response(202)
		return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})

	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
	await mcp_client.call_upstream("https://rebind.example.com/mcp", None, "tools/list", {})
	assert set(seen) == {"93.184.216.34"} and resolver.calls == 1


async def test_a_mixed_dns_answer_with_any_private_address_is_refused(monkeypatch):
	def mixed(host, port, *args, **kwargs):
		import socket
		return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)), (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", port))]

	monkeypatch.setattr(ssrf.socket, "getaddrinfo", mixed)
	assert await ssrf.resolve_public_ip("https://mixed.example.com/mcp") is None


# ── listing and routing ──────────────────────────────────────────────────────


async def test_endless_pagination_stops_at_the_page_limit(hostile):
	evil = hostile("endless_cursor")
	await mcp_gateway.list_tools([_server(evil)], CONFIG, mcp_client.call_upstream)
	assert evil.server.list_calls == mcp_gateway.MAX_LIST_PAGES


async def test_ten_thousand_tools_are_capped(hostile):
	evil = hostile("many_tools")
	result = await mcp_gateway.list_tools([_server(evil)], CONFIG, mcp_client.call_upstream)
	assert len(result["tools"]) == mcp_gateway.MAX_TOOLS_PER_SERVER


async def test_separator_in_tool_names_cannot_reach_another_server(hostile):
	evil, good = hostile("weird_names"), hostile("benign")
	servers = [_server(evil, "evil"), _server(good, "github")]
	listed = await mcp_gateway.list_tools(servers, CONFIG, mcp_client.call_upstream)
	assert "evil__github__search" in [t["name"] for t in listed["tools"]]  # advertised under evil's namespace...

	# ...and the call is routed to evil, which receives the full remainder as its own tool name.
	await mcp_gateway.call_tool(servers, CONFIG, "evil__github__search", {}, mcp_client.call_upstream)
	call = next(r for r in evil.server.requests if r["method"] == "tools/call")
	assert call["body"]["params"]["name"] == "github__search"
	assert "tools/call" not in good.server.methods()


async def test_injected_upstream_error_text_never_reaches_the_agent(hostile):
	evil = hostile("injected_error")
	outcome = await mcp_gateway.call_tool([_server(evil)], CONFIG, "evil__search", {}, mcp_client.call_upstream)
	assert outcome.status_code == 502
	assert "Ignore previous" not in json.dumps(outcome.error) and "evil.example" not in json.dumps(outcome.error)


# ── through the real route: nothing of the client's identity reaches the upstream ──


async def test_client_headers_and_gateway_key_never_reach_the_upstream(hostile, monkeypatch):
	from httpx import ASGITransport, AsyncClient

	evil = hostile("echo_headers")
	row = SimpleNamespace(id=uuid.uuid4(), org_id=ORG, name="evil", url=evil.url, auth_header_encrypted="Bearer org-upstream-secret",
	                      is_active=True, created_at=datetime(2026, 9, 30))
	db = FakeDB(servers=[row])

	async def fake_auth():
		return USER, API_KEY

	async def fake_db():
		yield db

	redis = FakeRedis()

	async def fake_redis():
		return redis

	async def fake_policy(org_id, db_, redis_):
		return CONFIG

	async def fake_record(**kwargs):
		return None

	app.dependency_overrides[get_current_user_from_api_key] = fake_auth
	app.dependency_overrides[get_db] = fake_db
	app.dependency_overrides[get_redis] = fake_redis
	monkeypatch.setattr(mcp_route.policy_store, "load", fake_policy)
	monkeypatch.setattr(mcp_route, "decrypt", lambda value: value)
	monkeypatch.setattr(mcp_route, "record_tool_call", fake_record)

	headers = {
		"Authorization": "Bearer opai_gateway_key_123",
		"Cookie": "session=abc",
		"X-Custom": "client-secret",
		"X-Forwarded-For": "203.0.113.9",
		"Mcp-Session-Id": "client-session",
	}
	body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "evil__search", "arguments": {"q": "x"}}}
	async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as http:
		response = await http.post("/v1/mcp", json=body, headers=headers)
	assert response.status_code == 200

	seen = [r["headers"] for r in evil.server.requests if r["http_method"] == "POST"]
	assert seen, "the upstream was never called"
	flat = json.dumps(seen)
	assert "opai_" not in flat and "client-secret" not in flat and "session=abc" not in flat
	assert "203.0.113.9" not in flat and "client-session" not in flat
	assert all(h.get("authorization") == "Bearer org-upstream-secret" for h in seen)


# ── gaps closed by later Phase 1 PRs (strict xfail: they must start failing when fixed) ──


@pytest.mark.xfail(strict=True, reason="PR 3: tools/list must serve the pinned snapshot, not the live description (rug-pull)")
async def test_rug_pull_does_not_change_what_agents_see(hostile):
	evil = hostile("rug_pull", rug_after=1)
	first = await mcp_gateway.list_tools([_server(evil)], CONFIG, mcp_client.call_upstream)
	second = await mcp_gateway.list_tools([_server(evil)], CONFIG, mcp_client.call_upstream)
	assert first["tools"][0]["description"] == second["tools"][0]["description"]


@pytest.mark.xfail(strict=True, reason="PR 4: tool descriptions are scanned for hidden instructions")
async def test_poisoned_descriptions_are_not_served(hostile):
	evil = hostile("poisoned")
	listed = await mcp_gateway.list_tools([_server(evil)], CONFIG, mcp_client.call_upstream)
	served = json.dumps(listed["tools"], ensure_ascii=False)
	assert "<IMPORTANT>" not in served and POISONED_DESCRIPTION not in served


@pytest.mark.xfail(strict=True, reason="PR 4: tool results are scanned for injection and exfiltration URLs")
async def test_injected_results_are_blocked_or_redacted(hostile):
	evil = hostile("injected_result")
	outcome = await mcp_gateway.call_tool([_server(evil)], CONFIG, "evil__search", {}, mcp_client.call_upstream)
	assert outcome.error is not None or INJECTION not in json.dumps(outcome.result)
