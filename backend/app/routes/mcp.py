"""MCP gateway endpoint: POST /v1/mcp (Streamable HTTP, JSON-RPC 2.0, MCP 2025-11-25).

Agents authenticate with an OpenProxyAI API key; tools from every active upstream server of the
key's organisation are exposed as "<server>__<tool>" and policy-checked per call.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import ProxyAuth, get_db, get_redis
from app.middleware.cors import parse_origins
from app.models.mcp_server import McpServer
from app.services.crypto_service import decrypt
from app.services.mcp_audit import record_tool_call
from app.services.mcp_client import call_upstream
from app.services.mcp_bundles import key_has_bundles, load_bundle_patterns
from app.services.mcp_gateway import UpstreamServer, call_tool, list_tools
from app.services.mcp_grants import (
	SCOPE_HEADER,
	Caller,
	ScopeHeaderError,
	build_access,
	load_grants,
	parse_scope_header,
)
from app.services.mcp_pinning import DbPinStore
from app.services.mcp_rate_limit import check_mcp_rate_limit
from app.services.security_events import SecurityEvent
from app.services.telemetry import telemetry
from app.services.mcp_taint import TaintContext, create_session, get_session, load_trust_rules, mark_tainted
from app.services.policy_service import policy_store

router = APIRouter(tags=["MCP Gateway"])

LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = {"2025-11-25", "2025-06-18", "2025-03-26"}
SERVER_INFO = {"name": "OpenProxyAI MCP Gateway", "version": "1.0.0"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
FORBIDDEN = -32005
RATE_LIMITED = -32006
BUNDLE_NOT_FOUND = -32008
SESSION_NOT_FOUND = -32010

MCP_PERMISSION = "proxy:mcp"


def _result(request_id: Any, result: dict) -> JSONResponse:
	return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id: Any, code: int, message: str, data: dict | None = None, status_code: int = 200) -> JSONResponse:
	error: dict[str, Any] = {"code": code, "message": message}
	if data is not None:
		error["data"] = data
	return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": error}, status_code=status_code)


def _origin_allowed(origin: str | None) -> bool:
	"""Browsers always send Origin, so a mismatch is a web page trying to drive the gateway
	(DNS rebinding / drive-by). Non-browser agents send none, which is allowed."""
	if origin is None:
		return True
	allowed = {o.rstrip("/").lower() for o in parse_origins(settings.CORS_ORIGINS)}
	return "*" in allowed or origin.rstrip("/").lower() in allowed


async def _active_servers(db: AsyncSession, org_id: uuid.UUID) -> list[UpstreamServer]:
	rows = await db.scalars(
		select(McpServer).where(McpServer.org_id == org_id, McpServer.is_active.is_(True)).order_by(McpServer.name)
	)
	return [
		UpstreamServer(
			id=row.id,
			pin_mode=row.pin_mode,
			scan_mode=row.scan_mode,
			name=row.name,
			url=row.url,
			auth_header=decrypt(row.auth_header_encrypted) if row.auth_header_encrypted else None,
		)
		for row in rows.all()
	]


@router.post("/v1/mcp")
async def mcp_endpoint(
	request: Request,
	auth: ProxyAuth,
	background_tasks: BackgroundTasks,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> Response:
	return await _serve(request, auth, background_tasks, db, redis, None)


@router.post("/v1/mcp/{slug}")
async def mcp_bundle_endpoint(
	slug: str,
	request: Request,
	auth: ProxyAuth,
	background_tasks: BackgroundTasks,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> Response:
	"""The same gateway, limited to the tools of one bundle the calling key is attached to."""
	return await _serve(request, auth, background_tasks, db, redis, slug)


async def _serve(
	request: Request,
	auth,
	background_tasks: BackgroundTasks,
	db: AsyncSession,
	redis: Redis,
	bundle_slug: str | None,
) -> Response:
	user, api_key = auth
	who = {"org_id": user.org_id, "user_id": user.id, "api_key_id": api_key.id}
	if not _origin_allowed(request.headers.get("origin")):
		telemetry.event(SecurityEvent("AI-UNAUTHORIZED-MCP", reason="origin_not_allowed", **who))
		return _error(None, FORBIDDEN, "Origin not allowed", status_code=403)
	if MCP_PERMISSION not in (api_key.permissions or []):
		telemetry.event(SecurityEvent("AI-UNAUTHORIZED-MCP", reason="missing_proxy_mcp_permission", **who))
		return _error(None, FORBIDDEN, f"API key lacks the {MCP_PERMISSION} permission", status_code=403)
	allowed, retry_after = await check_mcp_rate_limit(redis, api_key.id, settings.MCP_RATE_LIMIT_PER_MINUTE)
	if not allowed:
		telemetry.event(SecurityEvent("AI-RATE-LIMIT", reason="mcp_requests_per_minute", **who))
		response = _error(None, RATE_LIMITED, "Rate limit exceeded", status_code=429)
		response.headers["Retry-After"] = str(retry_after)
		return response
	try:
		scope = parse_scope_header(request.headers.getlist(SCOPE_HEADER))
	except ScopeHeaderError as exc:
		return _error(None, INVALID_REQUEST, str(exc), status_code=400)
	bundle: tuple[str, ...] | None = None
	if bundle_slug is None:
		if await key_has_bundles(db, user.org_id, api_key.id):
			telemetry.event(SecurityEvent("AI-UNAUTHORIZED-MCP", reason="bundle_confined_key_on_bare_endpoint", **who))
			return _error(None, FORBIDDEN, "This API key is confined to MCP bundles: use /v1/mcp/{bundle}", status_code=403)
	else:
		bundle = await load_bundle_patterns(db, user.org_id, api_key.id, bundle_slug)
		if bundle is None:
			return _error(None, BUNDLE_NOT_FOUND, "Bundle not found", status_code=404)
	try:
		message = await request.json()
	except ValueError:
		return _error(None, PARSE_ERROR, "Parse error", status_code=400)
	# JSON-RPC batching was removed in MCP 2025-06-18: one message per POST.
	if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
		return _error(None, INVALID_REQUEST, "Invalid Request", status_code=400)

	method: str = message["method"]
	params = message.get("params") or {}
	if "id" not in message:
		return Response(status_code=202)  # notification (e.g. notifications/initialized)
	request_id = message["id"]

	if method == "initialize":
		requested = params.get("protocolVersion") if isinstance(params, dict) else None
		version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION
		response = _result(request_id, {
			"protocolVersion": version,
			"capabilities": {"tools": {"listChanged": False}},
			"serverInfo": SERVER_INFO,
		})
		response.headers["Mcp-Session-Id"] = await create_session(redis, api_key.id)
		return response
	session_id = request.headers.get("mcp-session-id")
	session = None
	if session_id is not None:
		session = await get_session(redis, session_id, api_key.id)
		if session is None:  # unknown, expired or someone else's: the client must initialize again (MCP spec)
			return _error(request_id, SESSION_NOT_FOUND, "Session not found; send initialize", status_code=404)
	if method == "ping":
		return _result(request_id, {})
	if method not in ("tools/list", "tools/call"):
		return _error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")
	if not isinstance(params, dict):
		return _error(request_id, -32602, "params must be an object")

	servers = await _active_servers(db, user.org_id)
	config = await policy_store.load(user.org_id, db, redis)

	caller = Caller(user_id=user.id, role=user.role, team_id=getattr(api_key, "team_id", None), api_key_id=api_key.id)
	access = build_access(await load_grants(db, user.org_id), caller, scope, bundle)
	pins = DbPinStore(db, user.org_id)
	if method == "tools/list":
		listed = await list_tools(servers, config, call_upstream, pins, access)
		await db.commit()  # persists newly seen / drifted tool definitions
		return _result(request_id, listed)

	started = time.perf_counter()
	taint = TaintContext(rules=await load_trust_rules(db, user.org_id), session=session)
	outcome = await call_tool(servers, config, params.get("name"), params.get("arguments", {}), call_upstream, pins, access, taint)
	if outcome.taints_session and session is not None:
		await mark_tainted(redis, session.session_id)  # before answering: the next request must already see it
	outcome = replace(outcome, taint={
		"session": taint.label,
		"sink": isinstance(outcome.tool, str) and taint.rules.is_sink(outcome.tool),
		"taints_session": outcome.taints_session,
	})
	summary = access.summary()
	if bundle_slug is not None:
		summary = {**summary, "bundle": bundle_slug}
	outcome = replace(outcome, access=summary)
	background_tasks.add_task(
		record_tool_call,
		org_id=user.org_id,
		user_id=user.id,
		api_key_id=api_key.id,
		outcome=outcome,
		latency_ms=int((time.perf_counter() - started) * 1000),
	)
	if outcome.error is not None:
		return _error(request_id, outcome.error["code"], outcome.error["message"], outcome.error.get("data"))
	return _result(request_id, outcome.result or {})


@router.get("/v1/mcp")
@router.delete("/v1/mcp")
@router.get("/v1/mcp/{slug}")
@router.delete("/v1/mcp/{slug}")
async def mcp_no_stream(slug: str | None = None) -> Response:
	"""The gateway does not open server-initiated SSE streams or hold sessions (spec M1)."""
	return Response(status_code=405, headers={"Allow": "POST"})
