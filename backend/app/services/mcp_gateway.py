"""MCP gateway core: aggregate an org's upstream MCP servers behind one tool namespace.

Pure orchestration — the upstream caller is injected (``mcp_client.call_upstream`` in production)
so policy and routing are testable without a network. See the design:
docs/superpowers/specs/2026-09-30-mcp-gateway-design.md
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.services.mcp_client import McpUpstreamError
from app.services.policy_service import PolicyConfig, PolicyDecision, policy_service

TOOL_SEPARATOR = "__"
MAX_LIST_PAGES = 10

# JSON-RPC error codes (implementation-defined range for gateway errors).
ERR_INVALID_PARAMS = -32602
ERR_POLICY_BLOCKED = -32001
ERR_UPSTREAM = -32002

UpstreamCall = Callable[[str, str | None, str, dict | None], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class UpstreamServer:
    name: str
    url: str
    auth_header: str | None


@dataclass(frozen=True)
class ToolCallOutcome:
    """Everything the route needs to answer the call and write the audit row."""

    tool: str
    server: str | None
    status_code: int  # HTTP-equivalent for the audit log: 200, 400, 446 or 502
    decision: PolicyDecision | None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


async def _list_server_tools(server: UpstreamServer, call: UpstreamCall) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(MAX_LIST_PAGES):
        page = await call(server.url, server.auth_header, "tools/list", {"cursor": cursor} if cursor else {})
        tools.extend(page.get("tools") or [])
        cursor = page.get("nextCursor")
        if not cursor:
            break
    return tools


async def list_tools(servers: list[UpstreamServer], config: PolicyConfig, call: UpstreamCall) -> dict[str, Any]:
    """tools/list across every server; tools the policy would block are not advertised."""
    results = await asyncio.gather(*(_list_server_tools(s, call) for s in servers), return_exceptions=True)
    tools: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for server, result in zip(servers, results):
        if isinstance(result, McpUpstreamError):
            unavailable.append(server.name)
            continue
        if isinstance(result, BaseException):
            raise result
        for tool in result:
            name = f"{server.name}{TOOL_SEPARATOR}{tool['name']}"
            if policy_service.evaluate_tool_call(name, {}, config).allowed:
                tools.append({**tool, "name": name})
    response: dict[str, Any] = {"tools": tools}
    if unavailable:
        response["_meta"] = {"openproxyai/unavailableServers": unavailable}
    return response


def _invalid(tool: str, message: str) -> ToolCallOutcome:
    return ToolCallOutcome(tool=tool, server=None, status_code=400, decision=None,
                           error={"code": ERR_INVALID_PARAMS, "message": message})


async def call_tool(
    servers: list[UpstreamServer], config: PolicyConfig, name: Any, arguments: Any, call: UpstreamCall
) -> ToolCallOutcome:
    """tools/call: resolve the server, apply policy, forward, and describe what happened."""
    if not isinstance(name, str):
        return _invalid(str(name), "Tool name must be a string")
    if not isinstance(arguments, dict):
        return _invalid(name, "Tool arguments must be an object")
    server_name, sep, tool = name.partition(TOOL_SEPARATOR)
    server = next((s for s in servers if s.name == server_name), None)
    if not sep or not tool or server is None:
        return _invalid(name, f"Unknown tool: {name}")

    decision = policy_service.evaluate_tool_call(name, arguments, config)
    if not decision.allowed:
        return ToolCallOutcome(
            tool=name, server=server.name, status_code=446, decision=decision,
            error={
                "code": ERR_POLICY_BLOCKED,
                "message": decision.detail or "Blocked by organization policy",
                "data": {"reason_code": decision.reason_code, "triggered_rules": decision.triggered_rules or []},
            },
        )

    try:
        result = await call(server.url, server.auth_header, "tools/call", {"name": tool, "arguments": arguments})
    except McpUpstreamError as exc:
        return ToolCallOutcome(tool=name, server=server.name, status_code=502, decision=decision,
                               error={"code": ERR_UPSTREAM, "message": f"Upstream MCP server {server.name} failed: {exc}"})
    return ToolCallOutcome(tool=name, server=server.name, status_code=200, decision=decision, result=result)
