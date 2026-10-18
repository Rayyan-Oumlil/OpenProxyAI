"""Upstream MCP client: Streamable HTTP handshake, JSON and SSE responses, errors, SSRF."""

import json

import httpx
import pytest

from app.services import mcp_client

URL = "https://tools.example.com/mcp"


class FakeUpstream:
	"""Minimal Streamable HTTP MCP server. Records every request it receives."""

	def __init__(self, *, sse: bool = False, fail_method: str | None = None, status: int = 200) -> None:
		self.requests: list[httpx.Request] = []
		self.sse = sse
		self.fail_method = fail_method
		self.status = status

	def __call__(self, request: httpx.Request) -> httpx.Response:
		self.requests.append(request)
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
		monkeypatch.setattr(mcp_client, "is_safe_https_url", lambda url: True)
		return fake
	return install


async def test_handshake_then_request_with_session_and_version_headers(upstream):
	fake = upstream()
	result = await mcp_client.call_upstream(URL, "Bearer upstream-token", "tools/list", {})
	assert result == {"echo": "tools/list", "params": {}}
	methods = [json.loads(r.content)["method"] for r in fake.requests]
	assert methods == ["initialize", "notifications/initialized", "tools/list"]
	for r in fake.requests:
		assert "application/json" in r.headers["accept"] and "text/event-stream" in r.headers["accept"]
		assert r.headers["authorization"] == "Bearer upstream-token"
	for r in fake.requests[1:]:
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
	monkeypatch.setattr(mcp_client, "is_safe_https_url", lambda url: False)
	with pytest.raises(mcp_client.McpUpstreamError, match="rejected"):
		await mcp_client.call_upstream("https://10.0.0.5/mcp", None, "tools/list", {})
	assert fake.requests == []
