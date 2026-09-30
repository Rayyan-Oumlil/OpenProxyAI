"""MCP gateway endpoint: POST /v1/mcp (Streamable HTTP, JSON-RPC 2.0, MCP 2025-11-25).

Agents authenticate with an OpenProxyAI API key; tools from every active upstream server of the
key's organisation are exposed as "<server>__<tool>" and policy-checked per call.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import ProxyAuth, get_db, get_redis
from app.models.mcp_server import McpServer
from app.services.crypto_service import decrypt
from app.services.mcp_audit import record_tool_call
from app.services.mcp_client import call_upstream
from app.services.mcp_gateway import UpstreamServer, call_tool, list_tools
from app.services.policy_service import policy_store

router = APIRouter(tags=["MCP Gateway"])

LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = {"2025-11-25", "2025-06-18", "2025-03-26"}
SERVER_INFO = {"name": "OpenProxyAI MCP Gateway", "version": "1.0.0"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601


def _result(request_id: Any, result: dict) -> JSONResponse:
	return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id: Any, code: int, message: str, data: dict | None = None, status_code: int = 200) -> JSONResponse:
	error: dict[str, Any] = {"code": code, "message": message}
	if data is not None:
		error["data"] = data
	return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": error}, status_code=status_code)


async def _active_servers(db: AsyncSession, org_id: uuid.UUID) -> list[UpstreamServer]:
	rows = await db.scalars(
		select(McpServer).where(McpServer.org_id == org_id, McpServer.is_active.is_(True)).order_by(McpServer.name)
	)
	return [
		UpstreamServer(
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
	user, api_key = auth
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
		response.headers["Mcp-Session-Id"] = uuid.uuid4().hex
		return response
	if method == "ping":
		return _result(request_id, {})
	if method not in ("tools/list", "tools/call"):
		return _error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")
	if not isinstance(params, dict):
		return _error(request_id, -32602, "params must be an object")

	servers = await _active_servers(db, user.org_id)
	config = await policy_store.load(user.org_id, db, redis)

	if method == "tools/list":
		return _result(request_id, await list_tools(servers, config, call_upstream))

	started = time.perf_counter()
	outcome = await call_tool(servers, config, params.get("name"), params.get("arguments", {}), call_upstream)
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
async def mcp_no_stream() -> Response:
	"""The gateway does not open server-initiated SSE streams or hold sessions (spec M1)."""
	return Response(status_code=405, headers={"Allow": "POST"})
