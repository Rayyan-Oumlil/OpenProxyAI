"""Upstream MCP client: Streamable HTTP handshake, JSON and SSE responses, errors, SSRF."""

import asyncio
import json

import httpx
import pytest

from app.services import mcp_client

URL = "https://tools.example.com/mcp"
PUBLIC_IP = "93.184.216.34"


def _resolver(ip: str | None):
	async def resolve(url: str) -> str | None:
		return ip
	return resolve


class FakeUpstream:
	"""Minimal Streamable HTTP MCP server. Records every request it receives."""

	def __init__(self, *, sse: bool = False, fail_method: str | None = None, status: int = 200) -> None:
		self.requests: list[httpx.Request] = []
		self.sse = sse
		self.fail_method = fail_method
		self.status = status

	def __call__(self, request: httpx.Request) -> httpx.Response:
		self.requests.append(request)
		if request.method == "DELETE":
			return httpx.Response(204)
		body = json.loads(request.content)
		if "id" not in body:
			return httpx.Response(202)
		if self.status != 200:
			return httpx.Response(self.status, text="boom")
		if body["method"] == self.fail_method:
			payload = {"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32601, "message": "nope"}}
		elif body["method"] == "initialize":
			payload = {"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}}}
			return httpx.Response(200, json=payload, headers={"Mcp-Session-Id": "sess-123"})
		else:
			payload = {"jsonrpc": "2.0", "id": body["id"], "result": {"echo": body["method"], "params": body.get("params")}}
		if self.sse:
			note = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progress": 1}}
			text = f"event: message\ndata: {json.dumps(note)}\n\nevent: message\ndata: {json.dumps(payload)}\n\n"
			return httpx.Response(200, text=text, headers={"Content-Type": "text/event-stream"})
		return httpx.Response(200, json=payload)


@pytest.fixture
def upstream(monkeypatch):
	def install(**kwargs) -> FakeUpstream:
		fake = FakeUpstream(**kwargs)
		monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
		monkeypatch.setattr(mcp_client, "resolve_public_ip", _resolver(PUBLIC_IP))
		return fake
	return install


async def test_handshake_then_request_with_session_and_version_headers(upstream):
	fake = upstream()
	result = await mcp_client.call_upstream(URL, "Bearer upstream-token", "tools/list", {})
	assert result == {"echo": "tools/list", "params": {}}
	posts = [r for r in fake.requests if r.method == "POST"]
	methods = [json.loads(r.content)["method"] for r in posts]
	assert methods == ["initialize", "notifications/initialized", "tools/list"]
	for r in posts:
		assert "application/json" in r.headers["accept"] and "text/event-stream" in r.headers["accept"]
		assert r.headers["authorization"] == "Bearer upstream-token"
	for r in posts[1:]:
		assert r.headers["mcp-session-id"] == "sess-123"
		assert r.headers["mcp-protocol-version"] == "2025-11-25"


async def test_sse_response_returns_the_matching_message(upstream):
	upstream(sse=True)
	result = await mcp_client.call_upstream(URL, None, "tools/call", {"name": "x", "arguments": {}})
	assert result["echo"] == "tools/call"


async def test_json_rpc_error_raises_with_code(upstream):
	upstream(fail_method="tools/call")
	with pytest.raises(mcp_client.McpUpstreamError) as exc:
		await mcp_client.call_upstream(URL, None, "tools/call", {"name": "x"})
	assert exc.value.code == -32601


async def test_http_error_raises(upstream):
	upstream(status=500)
	with pytest.raises(mcp_client.McpUpstreamError, match="HTTP 500"):
		await mcp_client.call_upstream(URL, None, "tools/list", {})


async def test_no_authorization_header_when_none_configured(upstream):
	fake = upstream()
	await mcp_client.call_upstream(URL, None, "tools/list", {})
	assert all("authorization" not in r.headers for r in fake.requests)


async def test_unsafe_url_is_rejected_before_any_request(monkeypatch):
	fake = FakeUpstream()
	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
	monkeypatch.setattr(mcp_client, "resolve_public_ip", _resolver(None))
	with pytest.raises(mcp_client.McpUpstreamError, match="rejected"):
		await mcp_client.call_upstream("https://10.0.0.5/mcp", None, "tools/list", {})
	assert fake.requests == []


# -- transport hardening (design-specs A.1) -----------------------------------


async def test_connects_to_the_validated_ip_and_keeps_host_and_sni(upstream):
	fake = upstream()
	await mcp_client.call_upstream(URL, None, "tools/list", {})
	for r in fake.requests:
		assert r.url.host == PUBLIC_IP
		assert r.headers["host"] == "tools.example.com"
		assert r.extensions["sni_hostname"] == "tools.example.com"


async def test_the_hostname_is_resolved_once_per_call(monkeypatch, upstream):
	upstream()
	calls: list[str] = []

	async def resolve(url: str) -> str:
		calls.append(url)
		return PUBLIC_IP

	monkeypatch.setattr(mcp_client, "resolve_public_ip", resolve)
	await mcp_client.call_upstream(URL, None, "tools/list", {})
	assert len(calls) == 1


async def test_ipv6_address_is_bracketed_in_the_pinned_url(monkeypatch, upstream):
	fake = upstream()
	monkeypatch.setattr(mcp_client, "resolve_public_ip", _resolver("2606:2800:220:1:248:1893:25c8:1946"))
	await mcp_client.call_upstream("https://tools.example.com:8443/mcp", None, "tools/list", {})
	assert fake.requests[0].url.host == "2606:2800:220:1:248:1893:25c8:1946"
	assert fake.requests[0].headers["host"] == "tools.example.com:8443"


async def test_redirects_are_rejected_not_followed(monkeypatch):
	seen: list[httpx.Request] = []

	def fake(request: httpx.Request) -> httpx.Response:
		seen.append(request)
		return httpx.Response(302, headers={"Location": "https://169.254.169.254/latest/meta-data"})

	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
	monkeypatch.setattr(mcp_client, "resolve_public_ip", _resolver(PUBLIC_IP))
	with pytest.raises(mcp_client.McpUpstreamError, match="redirect"):
		await mcp_client.call_upstream(URL, None, "tools/list", {})
	assert [r.url.host for r in seen] == [PUBLIC_IP]


async def test_oversized_response_is_cut_off(monkeypatch):
	monkeypatch.setattr(mcp_client, "MAX_RESPONSE_BYTES", 1024)
	pulled: list[int] = []

	async def body():
		for _ in range(1000):
			pulled.append(1)
			yield b"x" * 512

	def fake(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, content=body(), headers={"Content-Type": "application/json"})

	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
	monkeypatch.setattr(mcp_client, "resolve_public_ip", _resolver(PUBLIC_IP))
	with pytest.raises(mcp_client.McpUpstreamError, match="too large"):
		await mcp_client.call_upstream(URL, None, "tools/list", {})
	assert len(pulled) < 10  # stopped reading long before the 500 KB the upstream wanted to send


async def test_slow_drip_hits_the_total_deadline(monkeypatch):
	monkeypatch.setattr(mcp_client, "TOTAL_TIMEOUT_SECONDS", 0.3)

	async def drip():
		while True:
			await asyncio.sleep(0.05)
			yield b" "

	def fake(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, content=drip(), headers={"Content-Type": "text/event-stream"})

	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
	monkeypatch.setattr(mcp_client, "resolve_public_ip", _resolver(PUBLIC_IP))
	with pytest.raises(mcp_client.McpUpstreamError, match="timed out"):
		await asyncio.wait_for(mcp_client.call_upstream(URL, None, "tools/list", {}), timeout=5)


async def test_upstream_session_is_closed_with_delete(upstream):
	fake = upstream()
	await mcp_client.call_upstream(URL, None, "tools/list", {})
	last = fake.requests[-1]
	assert last.method == "DELETE" and last.headers["mcp-session-id"] == "sess-123"


async def test_session_is_closed_even_when_the_request_fails(upstream):
	fake = upstream(fail_method="tools/call")
	with pytest.raises(mcp_client.McpUpstreamError):
		await mcp_client.call_upstream(URL, None, "tools/call", {"name": "x"})
	assert fake.requests[-1].method == "DELETE"


async def test_a_failing_delete_never_changes_the_result(monkeypatch):
	def fake(request: httpx.Request) -> httpx.Response:
		if request.method == "DELETE":
			raise httpx.ConnectError("boom")
		body = json.loads(request.content)
		if "id" not in body:
			return httpx.Response(202)
		headers = {"Mcp-Session-Id": "s"} if body["method"] == "initialize" else {}
		return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"ok": True}}, headers=headers)

	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
	monkeypatch.setattr(mcp_client, "resolve_public_ip", _resolver(PUBLIC_IP))
	assert await mcp_client.call_upstream(URL, None, "tools/list", {}) == {"ok": True}


async def test_no_delete_when_upstream_issued_no_session(monkeypatch):
	seen: list[str] = []

	def fake(request: httpx.Request) -> httpx.Response:
		seen.append(request.method)
		body = json.loads(request.content)
		if "id" not in body:
			return httpx.Response(202)
		return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})

	monkeypatch.setattr(mcp_client, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake)))
	monkeypatch.setattr(mcp_client, "resolve_public_ip", _resolver(PUBLIC_IP))
	await mcp_client.call_upstream(URL, None, "tools/list", {})
	assert "DELETE" not in seen
