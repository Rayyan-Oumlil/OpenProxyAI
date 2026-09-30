"""MCP gateway core: tool aggregation, namespacing, policy, routing, upstream failures."""

import pytest

from app.services import mcp_gateway
from app.services.mcp_client import McpUpstreamError
from app.services.policy_service import PolicyConfig

GITHUB = mcp_gateway.UpstreamServer(name="github", url="https://gh.example.com/mcp", auth_header="Bearer gh")
JIRA = mcp_gateway.UpstreamServer(name="jira", url="https://jira.example.com/mcp", auth_header=None)

TOOLS = {
	GITHUB.url: [
		{"name": "search", "description": "Search code", "inputSchema": {"type": "object"}},
		{"name": "delete_repo", "description": "Delete a repo", "inputSchema": {"type": "object"}},
	],
	JIRA.url: [{"name": "create_issue", "description": "New issue", "inputSchema": {"type": "object"}}],
}


class FakeUpstreams:
	def __init__(self, broken: set[str] | None = None, pages: bool = False) -> None:
		self.calls: list[tuple[str, str | None, str, dict | None]] = []
		self.broken = broken or set()
		self.pages = pages

	async def __call__(self, url, auth_header, method, params):
		self.calls.append((url, auth_header, method, params))
		if url in self.broken:
			raise McpUpstreamError("connection refused")
		if method == "tools/list":
			tools = TOOLS[url]
			if self.pages and not (params or {}).get("cursor"):
				return {"tools": tools[:1], "nextCursor": "p2"}
			if self.pages:
				return {"tools": tools[1:]}
			return {"tools": tools}
		if method == "tools/call":
			return {"content": [{"type": "text", "text": f"ran {params['name']}"}], "isError": False}
		raise AssertionError(method)


def _cfg(**kw) -> PolicyConfig:
	return PolicyConfig(**{"enforcement_mode": "enforce", "pii_detection_enabled": True, **kw})


async def test_tools_are_aggregated_and_namespaced():
	result = await mcp_gateway.list_tools([GITHUB, JIRA], _cfg(), FakeUpstreams())
	names = [t["name"] for t in result["tools"]]
	assert names == ["github__search", "github__delete_repo", "jira__create_issue"]
	assert result["tools"][0]["description"] == "Search code"
	assert "_meta" not in result


async def test_paginated_upstreams_are_followed():
	result = await mcp_gateway.list_tools([GITHUB], _cfg(), FakeUpstreams(pages=True))
	assert [t["name"] for t in result["tools"]] == ["github__search", "github__delete_repo"]


async def test_policy_hides_disallowed_tools_from_the_list():
	cfg = _cfg(mcp_allowed_tools=["github__*"], mcp_blocked_tools=["*__delete_*"])
	result = await mcp_gateway.list_tools([GITHUB, JIRA], cfg, FakeUpstreams())
	assert [t["name"] for t in result["tools"]] == ["github__search"]


async def test_a_broken_upstream_is_reported_not_hidden():
	upstreams = FakeUpstreams(broken={JIRA.url})
	result = await mcp_gateway.list_tools([GITHUB, JIRA], _cfg(), upstreams)
	assert [t["name"] for t in result["tools"]] == ["github__search", "github__delete_repo"]
	assert result["_meta"] == {"openproxyai/unavailableServers": ["jira"]}


async def test_call_is_routed_with_the_upstream_tool_name_and_auth():
	upstreams = FakeUpstreams()
	outcome = await mcp_gateway.call_tool([GITHUB, JIRA], _cfg(), "github__search", {"q": "rls"}, upstreams)
	assert outcome.error is None and outcome.server == "github"
	assert outcome.result["content"][0]["text"] == "ran search"
	assert upstreams.calls == [(GITHUB.url, "Bearer gh", "tools/call", {"name": "search", "arguments": {"q": "rls"}})]


async def test_blocked_call_never_reaches_the_upstream():
	upstreams = FakeUpstreams()
	cfg = _cfg(mcp_blocked_tools=["*__delete_*"])
	outcome = await mcp_gateway.call_tool([GITHUB], cfg, "github__delete_repo", {}, upstreams)
	assert upstreams.calls == []
	assert outcome.error["code"] == mcp_gateway.ERR_POLICY_BLOCKED
	assert outcome.error["data"]["reason_code"] == "tool_blocked"
	assert outcome.status_code == 446


async def test_pii_in_arguments_blocks_the_call():
	outcome = await mcp_gateway.call_tool([JIRA], _cfg(), "jira__create_issue", {"body": "SSN 123-45-6789"}, FakeUpstreams())
	assert outcome.error["data"]["reason_code"] == "pii_detected"


async def test_log_only_mode_forwards_and_records_the_violation():
	cfg = _cfg(enforcement_mode="log_only", mcp_blocked_tools=["*__delete_*"])
	outcome = await mcp_gateway.call_tool([GITHUB], cfg, "github__delete_repo", {}, FakeUpstreams())
	assert outcome.error is None and outcome.decision.action == "log_only"


@pytest.mark.parametrize("name", ["search", "gitlab__search", "github__", "__search"])
async def test_unknown_or_malformed_tool_names_are_invalid_params(name):
	outcome = await mcp_gateway.call_tool([GITHUB], _cfg(), name, {}, FakeUpstreams())
	assert outcome.error["code"] == mcp_gateway.ERR_INVALID_PARAMS
	assert outcome.status_code == 400


async def test_non_object_arguments_are_invalid_params():
	outcome = await mcp_gateway.call_tool([GITHUB], _cfg(), "github__search", ["not", "an", "object"], FakeUpstreams())
	assert outcome.error["code"] == mcp_gateway.ERR_INVALID_PARAMS


async def test_upstream_failure_becomes_a_gateway_error():
	outcome = await mcp_gateway.call_tool([GITHUB], _cfg(), "github__search", {}, FakeUpstreams(broken={GITHUB.url}))
	assert outcome.error["code"] == mcp_gateway.ERR_UPSTREAM and outcome.status_code == 502
