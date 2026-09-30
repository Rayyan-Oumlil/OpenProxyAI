"""Client for upstream MCP servers over the Streamable HTTP transport (MCP 2025-11-25).

Each call is self-contained: initialize → notifications/initialized → the request, carrying the
server's Mcp-Session-Id and the negotiated MCP-Protocol-Version. Stateless by design (spec M1).
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.utils.ssrf import is_safe_https_url

PROTOCOL_VERSION = "2025-11-25"
CLIENT_INFO = {"name": "openproxyai-mcp-gateway", "version": "1.0.0"}
UPSTREAM_TIMEOUT_SECONDS = 20.0

_ACCEPT = "application/json, text/event-stream"


class McpUpstreamError(Exception):
    """Transport failure or JSON-RPC error from an upstream MCP server."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS, follow_redirects=False)


def _parse_sse(text: str, request_id: int) -> dict[str, Any]:
    """Return the JSON-RPC message in an SSE body whose id matches ``request_id``."""
    for event in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in event.split("\n") if line.startswith("data:"))
        if not data:
            continue
        message = json.loads(data)
        if message.get("id") == request_id:
            return message
    raise McpUpstreamError(f"upstream SSE stream ended without a response to request {request_id}")


async def _request(
    client: httpx.AsyncClient, url: str, headers: dict[str, str], request_id: int, method: str, params: dict | None
) -> tuple[dict[str, Any], httpx.Response]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    try:
        response = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise McpUpstreamError(f"upstream request failed: {exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        raise McpUpstreamError(f"upstream returned HTTP {response.status_code} for {method}")
    content_type = response.headers.get("content-type", "")
    try:
        message = (
            _parse_sse(response.text, request_id)
            if content_type.startswith("text/event-stream")
            else response.json()
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise McpUpstreamError(f"upstream sent an unreadable response to {method}") from exc
    if "error" in message:
        error = message["error"] or {}
        raise McpUpstreamError(str(error.get("message", "upstream error")), code=error.get("code"))
    return message.get("result") or {}, response


async def call_upstream(url: str, auth_header: str | None, method: str, params: dict | None) -> dict[str, Any]:
    """Run ``method`` on the MCP server at ``url`` and return its JSON-RPC ``result``."""
    if not is_safe_https_url(url):
        raise McpUpstreamError("upstream URL rejected: must be HTTPS and resolve to a public address")

    headers = {"Accept": _ACCEPT, "Content-Type": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header

    async with _make_client() as client:
        init_result, init_response = await _request(
            client, url, headers, 1, "initialize",
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
        )
        headers["MCP-Protocol-Version"] = str(init_result.get("protocolVersion") or PROTOCOL_VERSION)
        session_id = init_response.headers.get("mcp-session-id")
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        try:
            ack = await client.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers)
        except httpx.HTTPError as exc:
            raise McpUpstreamError(f"upstream request failed: {exc.__class__.__name__}") from exc
        if ack.status_code >= 400:
            raise McpUpstreamError(f"upstream returned HTTP {ack.status_code} for notifications/initialized")

        result, _ = await _request(client, url, headers, 2, method, params)
        return result
