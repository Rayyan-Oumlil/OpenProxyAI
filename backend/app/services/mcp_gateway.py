"""MCP gateway core: aggregate an org's upstream MCP servers behind one tool namespace.

Pure orchestration — the upstream caller is injected (``mcp_client.call_upstream`` in production)
so policy and routing are testable without a network. See the design:
docs/superpowers/specs/2026-09-30-mcp-gateway-design.md
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.mcp_client import McpUpstreamError
from app.services.mcp_grants import ToolAccess
from app.services.mcp_pinning import PIN_OFF, ToolPin, call_gate, served_snapshot
from app.services.mcp_scanner import SCAN_BLOCK, SCAN_OFF, SCAN_REDACT, scan_value
from app.services.policy_service import PolicyConfig, PolicyDecision, policy_service

logger = logging.getLogger(__name__)

TOOL_SEPARATOR = "__"
MAX_LIST_PAGES = 10
MAX_TOOLS_PER_SERVER = 1000  # a hostile server must not flood the agent context with tools

# JSON-RPC error codes (implementation-defined range for gateway errors).
ERR_INVALID_PARAMS = -32602
ERR_POLICY_BLOCKED = -32001
ERR_UPSTREAM = -32002
ERR_OUTPUT_BLOCKED = -32007  # scan_mode=block: the tool result carried injection
ERR_TOOL_PIN = -32004  # tool not approved (pending, drifted or blocked) under pin_mode=enforce

UpstreamCall = Callable[[str, str | None, str, dict | None], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class UpstreamServer:
    name: str
    url: str
    auth_header: str | None
    id: uuid.UUID | None = None
    pin_mode: str = PIN_OFF
    scan_mode: str = SCAN_OFF


class PinStore(Protocol):
    """Pin state for tools of upstream servers (see mcp_pinning.DbPinStore)."""

    async def reconcile(self, server: UpstreamServer, live: list[dict[str, Any]]) -> dict[str, ToolPin]: ...

    async def get(self, server: UpstreamServer, tool_name: str) -> ToolPin | None: ...


@dataclass(frozen=True)
class ToolCallOutcome:
    """Everything the route needs to answer the call and write the audit row."""

    tool: str
    server: str | None
    status_code: int  # HTTP-equivalent for the audit log: 200, 400, 446 or 502
    decision: PolicyDecision | None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    scan_findings: tuple[str, ...] = ()  # categories found in the result (never the text itself)
    access: dict[str, Any] | None = None  # grants and request scope that applied (set by the route)
    pin_status: str | None = None  # pending | approved | drifted | blocked | unpinned; None when pinning is off


async def list_server_tools(server: UpstreamServer, call: UpstreamCall) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(MAX_LIST_PAGES):
        page = await call(server.url, server.auth_header, "tools/list", {"cursor": cursor} if cursor else {})
        tools.extend(t for t in page.get("tools") or [] if isinstance(t, dict) and isinstance(t.get("name"), str))
        cursor = page.get("nextCursor")
        if not cursor:
            break
        if len(tools) >= MAX_TOOLS_PER_SERVER:
            break
    if len(tools) > MAX_TOOLS_PER_SERVER:
        logger.warning("MCP upstream %s advertised %d tools; truncated to %d", server.name, len(tools), MAX_TOOLS_PER_SERVER)
        tools = tools[:MAX_TOOLS_PER_SERVER]
    return tools


def _scan_definition(server: UpstreamServer, tool: dict[str, Any]) -> dict[str, Any] | None:
    """Apply scan_mode to a tool definition about to be shown to an agent. None means hide it."""
    if server.scan_mode == SCAN_OFF:
        return tool
    scanned = scan_value(tool, redact=server.scan_mode == SCAN_REDACT)
    if not scanned.flagged:
        return tool
    logger.warning("MCP tool %s.%s description flagged (%s): mode=%s", server.name, tool["name"], ",".join(scanned.categories), server.scan_mode)
    if server.scan_mode == SCAN_BLOCK:
        return None
    return {**scanned.value, "name": tool["name"]} if server.scan_mode == SCAN_REDACT else tool


async def list_tools(
    servers: list[UpstreamServer],
    config: PolicyConfig,
    call: UpstreamCall,
    pins: PinStore | None = None,
    access: ToolAccess | None = None,
) -> dict[str, Any]:
    """tools/list across every server; tools the policy would block are not advertised.

    With pinning on, agents see the approved snapshot of each tool, never the live description.
    """
    results = await asyncio.gather(*(list_server_tools(s, call) for s in servers), return_exceptions=True)
    tools: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for server, result in zip(servers, results):
        if isinstance(result, McpUpstreamError):
            unavailable.append(server.name)
            continue
        if isinstance(result, BaseException):
            raise result
        if pins is not None and server.pin_mode != PIN_OFF:
            pinned = await pins.reconcile(server, result)
            result = [snap for t in result if (snap := served_snapshot(pinned.get(t.get("name")), server.pin_mode))]
        for tool in result:
            name = f"{server.name}{TOOL_SEPARATOR}{tool['name']}"
            if not policy_service.evaluate_tool_call(name, {}, config).allowed:
                continue
            if access is not None and not access.check(name).allowed:
                continue
            tool = _scan_definition(server, tool)
            if tool is not None:
                tools.append({**tool, "name": name})
    response: dict[str, Any] = {"tools": tools}
    if unavailable:
        response["_meta"] = {"openproxyai/unavailableServers": unavailable}
    return response


def _invalid(tool: str, message: str) -> ToolCallOutcome:
    return ToolCallOutcome(tool=tool, server=None, status_code=400, decision=None,
                           error={"code": ERR_INVALID_PARAMS, "message": message})


async def call_tool(
    servers: list[UpstreamServer],
    config: PolicyConfig,
    name: Any,
    arguments: Any,
    call: UpstreamCall,
    pins: PinStore | None = None,
    access: ToolAccess | None = None,
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

    if access is not None:
        verdict = access.check(name)
        if not verdict.allowed:
            return ToolCallOutcome(
                tool=name, server=server.name, status_code=446, decision=decision,
                error={
                    "code": ERR_POLICY_BLOCKED,
                    "message": f"Tool {name} is not available to this caller",
                    "data": {"reason_code": verdict.reason, "triggered_rules": ["tool_grants"]},
                },
            )

    pin_status: str | None = None
    if pins is not None and server.pin_mode != PIN_OFF:
        allowed, pin_status = call_gate(await pins.get(server, tool), server.pin_mode)
        if not allowed:
            return ToolCallOutcome(
                tool=name, server=server.name, status_code=446, decision=decision, pin_status=pin_status,
                error={
                    "code": ERR_TOOL_PIN,
                    "message": f"Tool {name} is not approved ({pin_status}); ask an administrator to review it",
                    "data": {"reason_code": f"tool_pin_{pin_status}"},
                },
            )

    try:
        result = await call(server.url, server.auth_header, "tools/call", {"name": tool, "arguments": arguments})
    except McpUpstreamError as exc:
        # The upstream's own error text can carry prompt-injection or internals; log it, never forward it.
        logger.warning("MCP upstream %s failed on tools/call: %s", server.name, exc)
        return ToolCallOutcome(tool=name, server=server.name, status_code=502, decision=decision, pin_status=pin_status,
                               error={"code": ERR_UPSTREAM, "message": f"Upstream MCP server {server.name} unavailable"})
    findings: tuple[str, ...] = ()
    if server.scan_mode != SCAN_OFF:
        scanned = scan_value(result, redact=server.scan_mode == SCAN_REDACT)
        findings = scanned.categories
        if scanned.flagged:
            logger.warning("MCP result of %s flagged (%s): mode=%s", name, ",".join(findings), server.scan_mode)
        if scanned.flagged and server.scan_mode == SCAN_BLOCK:
            return ToolCallOutcome(
                tool=name, server=server.name, status_code=446, decision=decision, pin_status=pin_status,
                scan_findings=findings,
                error={
                    "code": ERR_OUTPUT_BLOCKED,
                    "message": f"Result of {name} was withheld: it looked like a prompt injection",
                    "data": {"reason_code": "tool_output_flagged", "categories": list(findings)},
                },
            )
        if server.scan_mode == SCAN_REDACT:
            result = scanned.value
    return ToolCallOutcome(
        tool=name, server=server.name, status_code=200, decision=decision, result=result,
        pin_status=pin_status, scan_findings=findings,
    )
