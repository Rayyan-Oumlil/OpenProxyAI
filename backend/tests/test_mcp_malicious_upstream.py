"""The gateway against a hostile upstream MCP server (tests/fixtures/malicious_mcp.py).

Real HTTP, real client, real gateway code: only DNS resolution is stubbed (the fixture listens on
127.0.0.1, which the SSRF guard would otherwise refuse). """

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
from app.services.mcp_taint import TrustRules
from app.services.policy_service import PolicyConfig
from app.utils import ssrf
from tests.conftest import FakeRedis
from tests.fixtures.malicious_mcp import INJECTION, METADATA_URL, RebindingResolver, RunningMaliciousMcp
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
	                      is_active=True, pin_mode="off", scan_mode="off", created_at=datetime(2026, 9, 30))
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
	async def no_grants(db_, org_id):
		return []

	async def no_bundles(db_, org_id, api_key_id):
		return False

	async def no_rules(db_, org_id):
		return TrustRules()

	monkeypatch.setattr(mcp_route, "load_trust_rules", no_rules)
	monkeypatch.setattr(mcp_route, "load_grants", no_grants)
	monkeypatch.setattr(mcp_route, "key_has_bundles", no_bundles)
	monkeypatch.setattr(mcp_route.policy_store, "load", fake_policy)
	monkeypatch.setattr(mcp_route, "decrypt", lambda value: value)
	monkeypatch.setattr(mcp_route, "record_tool_call", fake_record)

	headers = {
		"Authorization": "Bearer opai_gateway_key_123",
		"Cookie": "session=abc",
		"X-Custom": "client-secret",
		"X-Forwarded-For": "203.0.113.9",
	}
	body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "evil__search", "arguments": {"q": "x"}}}
	async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test") as http:
		init = await http.post("/v1/mcp", json={"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}, headers=headers)
		client_session = init.headers["mcp-session-id"]
		response = await http.post("/v1/mcp", json=body, headers={**headers, "Mcp-Session-Id": client_session})
	assert response.status_code == 200

	seen = [r["headers"] for r in evil.server.requests if r["http_method"] == "POST"]
	assert seen, "the upstream was never called"
	flat = json.dumps(seen)
	assert "opai_" not in flat and "client-secret" not in flat and "session=abc" not in flat
	assert "203.0.113.9" not in flat and client_session not in flat
	assert all(h.get("authorization") == "Bearer org-upstream-secret" for h in seen)


# -- injection carried by tool descriptions and results (scan_mode) ---------------------------------


def _scanning(running: RunningMaliciousMcp, mode: str, name: str = "evil") -> UpstreamServer:
	return UpstreamServer(name=name, url=running.url, auth_header=None, scan_mode=mode)


async def test_poisoned_descriptions_are_hidden_in_block_mode(hostile):
	evil = hostile("poisoned")
	listed = await mcp_gateway.list_tools([_scanning(evil, "block")], CONFIG, mcp_client.call_upstream)
	assert listed["tools"] == []


async def test_poisoned_descriptions_are_sanitised_in_redact_mode(hostile):
	evil = hostile("poisoned")
	listed = await mcp_gateway.list_tools([_scanning(evil, "redact")], CONFIG, mcp_client.call_upstream)
	(tool,) = listed["tools"]
	assert tool["name"] == "evil__search"
	assert "<IMPORTANT>" not in tool["description"] and chr(0xE0041) not in tool["description"]
	assert tool["description"].startswith("Search the web.")


async def test_poisoned_descriptions_pass_through_in_log_mode_but_are_reported(hostile, caplog):
	evil = hostile("poisoned")
	with caplog.at_level("WARNING", logger="app.services.mcp_gateway"):
		listed = await mcp_gateway.list_tools([_scanning(evil, "log")], CONFIG, mcp_client.call_upstream)
	assert "<IMPORTANT>" in listed["tools"][0]["description"]
	assert "unicode_tag" in caplog.text and "SECRET" not in caplog.text and "id_rsa" not in caplog.text


async def test_injected_results_are_withheld_in_block_mode(hostile):
	evil = hostile("injected_result")
	outcome = await mcp_gateway.call_tool([_scanning(evil, "block")], CONFIG, "evil__search", {}, mcp_client.call_upstream)
	assert outcome.status_code == 446 and outcome.result is None
	assert outcome.error["code"] == mcp_gateway.ERR_OUTPUT_BLOCKED == -32007
	assert set(outcome.scan_findings) >= {"instruction_override", "markdown_exfil"}
	assert "SECRET_TOKEN" not in json.dumps(outcome.error)


async def test_injected_results_are_sanitised_in_redact_mode(hostile):
	evil = hostile("injected_result")
	outcome = await mcp_gateway.call_tool([_scanning(evil, "redact")], CONFIG, "evil__search", {}, mcp_client.call_upstream)
	assert outcome.status_code == 200
	text = outcome.result["content"][0]["text"]
	assert "SECRET_TOKEN" not in text and "Ignore previous" not in text and "[redacted:" in text
	assert outcome.scan_findings


async def test_injected_results_are_delivered_but_flagged_in_log_mode(hostile):
	evil = hostile("injected_result")
	outcome = await mcp_gateway.call_tool([_scanning(evil, "log")], CONFIG, "evil__search", {}, mcp_client.call_upstream)
	assert outcome.status_code == 200 and INJECTION in outcome.result["content"][0]["text"]
	assert outcome.scan_findings


async def test_scan_mode_off_changes_nothing(hostile):
	evil = hostile("injected_result")
	outcome = await mcp_gateway.call_tool([_scanning(evil, "off")], CONFIG, "evil__search", {}, mcp_client.call_upstream)
	assert outcome.status_code == 200 and outcome.scan_findings == ()


async def test_clean_results_are_untouched_in_every_mode(hostile):
	evil = hostile("benign")
	for mode in ("log", "redact", "block"):
		outcome = await mcp_gateway.call_tool([_scanning(evil, mode)], CONFIG, "evil__search", {}, mcp_client.call_upstream)
		assert outcome.status_code == 200 and outcome.result["content"][0]["text"] == "ok" and outcome.scan_findings == ()


async def test_scan_findings_reach_the_audit_row(hostile, monkeypatch):
	from app.services import mcp_audit

	rows = []

	class Session:
		info: dict = {}

		async def __aenter__(self):
			return self

		async def __aexit__(self, *exc):
			return False

		def add(self, row):
			rows.append(row)

		async def commit(self):
			return None

	monkeypatch.setattr(mcp_audit, "org_scoped_session", lambda org_id: Session())
	evil = hostile("injected_result")
	outcome = await mcp_gateway.call_tool([_scanning(evil, "block")], CONFIG, "evil__search", {}, mcp_client.call_upstream)
	await mcp_audit.record_tool_call(org_id=ORG, user_id=USER.id, api_key_id=None, outcome=outcome, latency_ms=1)
	assert "markdown_exfil" in rows[0].request_metadata["scan_findings"]
	assert rows[0].status_code == 446 and "SECRET_TOKEN" not in json.dumps(rows[0].request_metadata)
