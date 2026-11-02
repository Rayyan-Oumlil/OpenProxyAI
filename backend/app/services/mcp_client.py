"""Client for upstream MCP servers over the Streamable HTTP transport (MCP 2025-11-25).

Each call is self-contained: initialize → notifications/initialized → the request, carrying the
server's Mcp-Session-Id and the negotiated MCP-Protocol-Version. Stateless by design (spec M1).

Hardening (design-specs A.1): the hostname is resolved once, off the event loop, and every request of
the call connects to that validated IP (Host header and TLS SNI keep the original name), so a second
DNS answer cannot redirect us to an internal address. Redirects are rejected, the body is read with a
size cap, the whole call has one deadline, and the upstream session is closed with a DELETE.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.utils.ssrf import resolve_public_ip

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-11-25"
CLIENT_INFO = {"name": "openproxyai-mcp-gateway", "version": "1.0.0"}
UPSTREAM_TIMEOUT_SECONDS = 20.0  # per network phase (connect/read/write)
TOTAL_TIMEOUT_SECONDS = 30.0  # whole call: handshake + request, however slowly the upstream drips
CLOSE_TIMEOUT_SECONDS = 5.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

_ACCEPT = "application/json, text/event-stream"
MAX_ERROR_TEXT = 200


class McpUpstreamError(Exception):
    """Transport failure or JSON-RPC error from an upstream MCP server.

    The message is for logs only; the gateway never forwards it to the agent.
    """

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _PinnedTarget:
    url: str  # https://<validated ip>[:port]/path
    host_header: str  # original authority, so virtual hosting still works
    sni: str  # original hostname, so the certificate is verified against the name, not the IP


def _safe_text(value: object) -> str:
    """Upstream free text is attacker-controlled: drop control characters (log injection) and truncate."""
    text = "".join(ch for ch in str(value) if ch.isprintable())
    return text[:MAX_ERROR_TEXT]


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS, follow_redirects=False)


def _pin(url: str, ip: str) -> _PinnedTarget:
    parsed = urlparse(url)
    port = f":{parsed.port}" if parsed.port else ""
    ip_host = f"[{ip}]" if ":" in ip else ip
    return _PinnedTarget(
        url=parsed._replace(netloc=f"{ip_host}{port}").geturl(),
        host_header=f"{parsed.hostname}{port}",
        sni=parsed.hostname or "",
    )


def _parse_sse(text: str, request_id: int) -> dict[str, Any]:
    """Return the JSON-RPC message in an SSE body whose id matches ``request_id``."""
    for event in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in event.split("\n") if line.startswith("data:"))
        if not data:
            continue
        message = json.loads(data)
        if isinstance(message, dict) and message.get("id") == request_id:
            return message
    raise McpUpstreamError(f"upstream SSE stream ended without a response to request {request_id}")


async def _send(
    client: httpx.AsyncClient, method: str, target: _PinnedTarget, headers: dict[str, str], body: dict | None = None
) -> tuple[int, httpx.Headers, bytes]:
    """One request to the pinned IP. Never follows redirects; reads at most MAX_RESPONSE_BYTES."""
    try:
        async with client.stream(
            method,
            target.url,
            json=body,
            headers={**headers, "Host": target.host_header, "Accept-Encoding": "identity"},
            extensions={"sni_hostname": target.sni},
        ) as response:
            if 300 <= response.status_code < 400:
                raise McpUpstreamError(f"upstream redirect rejected (HTTP {response.status_code})")
            if response.status_code >= 400:
                return response.status_code, response.headers, b""
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                # A compressed body could expand far past the cap before we count it.
                raise McpUpstreamError("upstream used an unsupported content-encoding")
            declared = response.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > MAX_RESPONSE_BYTES:
                raise McpUpstreamError("upstream response too large")
            chunks: list[bytes] = []
            received = 0
            async for chunk in response.aiter_bytes():
                received += len(chunk)
                if received > MAX_RESPONSE_BYTES:
                    raise McpUpstreamError("upstream response too large")
                chunks.append(chunk)
            return response.status_code, response.headers, b"".join(chunks)
    except httpx.HTTPError as exc:
        raise McpUpstreamError(f"upstream request failed: {exc.__class__.__name__}") from exc


async def _request(
    client: httpx.AsyncClient,
    target: _PinnedTarget,
    headers: dict[str, str],
    request_id: int,
    method: str,
    params: dict | None,
) -> tuple[dict[str, Any], httpx.Headers]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    status, response_headers, raw = await _send(client, "POST", target, headers, body)
    if status >= 400:
        raise McpUpstreamError(f"upstream returned HTTP {status} for {method}")
    try:
        text = raw.decode("utf-8")
        message = (
            _parse_sse(text, request_id)
            if response_headers.get("content-type", "").startswith("text/event-stream")
            else json.loads(text)
        )
    except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError are both ValueErrors
        raise McpUpstreamError(f"upstream sent an unreadable response to {method}") from exc
    if not isinstance(message, dict):
        raise McpUpstreamError(f"upstream sent an unreadable response to {method}")
    if "error" in message:
        error = message["error"] if isinstance(message["error"], dict) else {}
        code = error.get("code")
        raise McpUpstreamError(_safe_text(error.get("message", "upstream error")), code=code if isinstance(code, int) else None)
    result = message.get("result") or {}
    if not isinstance(result, dict):
        raise McpUpstreamError(f"upstream sent an unreadable response to {method}")
    return result, response_headers


async def _close_session(client: httpx.AsyncClient, target: _PinnedTarget, headers: dict[str, str]) -> None:
    """Best-effort DELETE so the upstream can free the session. Must never change the call's outcome."""
    try:
        async with asyncio.timeout(CLOSE_TIMEOUT_SECONDS):
            await _send(client, "DELETE", target, headers)
    except Exception as exc:  # noqa: BLE001 - cleanup only; CancelledError is not an Exception
        logger.debug("MCP upstream session close failed: %s", exc.__class__.__name__)


async def call_upstream(url: str, auth_header: str | None, method: str, params: dict | None) -> dict[str, Any]:
    """Run ``method`` on the MCP server at ``url`` and return its JSON-RPC ``result``."""
    headers = {"Accept": _ACCEPT, "Content-Type": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header

    session_headers: dict[str, str] | None = None
    target: _PinnedTarget | None = None
    async with _make_client() as client:
        try:
            async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
                ip = await resolve_public_ip(url)  # inside the deadline: a slow resolver must not hang the call
                if ip is None:
                    raise McpUpstreamError("upstream URL rejected: must be HTTPS and resolve to a public address")
                target = _pin(url, ip)
                init_result, init_headers = await _request(
                    client, target, headers, 1, "initialize",
                    {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
                )
                session_headers = {
                    **headers,
                    "MCP-Protocol-Version": str(init_result.get("protocolVersion") or PROTOCOL_VERSION),
                }
                if session_id := init_headers.get("mcp-session-id"):
                    session_headers = {**session_headers, "Mcp-Session-Id": session_id}

                ack_status, _, _ = await _send(
                    client, "POST", target, session_headers, {"jsonrpc": "2.0", "method": "notifications/initialized"}
                )
                if ack_status >= 400:
                    raise McpUpstreamError(f"upstream returned HTTP {ack_status} for notifications/initialized")

                result, _ = await _request(client, target, session_headers, 2, method, params)
                return result
        except TimeoutError as exc:
            raise McpUpstreamError("upstream timed out") from exc
        finally:
            if target is not None and session_headers and "Mcp-Session-Id" in session_headers:
                await _close_session(client, target, session_headers)
