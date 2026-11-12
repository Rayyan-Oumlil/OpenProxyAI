"""WS /v1/realtime: the OpenAI Realtime API through the gateway (Phase 5).

The client speaks the provider's own protocol; the gateway authenticates it, applies the org's policy and limits to what it sends,
bills each response from the usage the provider reports, and ends the session when the key stops being valid or time runs out.
The per-event rules live in ``services/realtime_relay``; this module is the handshake and the wiring.

Choices worth knowing:

- Credentials come from the ``Authorization`` header, or from a WebSocket subprotocol (``openai-insecure-api-key.<key>``) for
  browsers, which cannot set headers. Never from the URL: URLs end up in logs.
- Only OpenAI, only the provider's own endpoint. A key with a custom endpoint is not used (its connection guard is HTTP-only).
- An org that enforces response guardrails cannot use realtime: the answer streams out as it is spoken and cannot be held back.
- No database connection is held while a session is live.
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.database import AsyncSessionLocal
from app.services import llm_service as ls
from app.services import realtime_pricing
from app.services.auth_service import validate_api_key
from app.services.classification_service import classify_text
from app.services.modality_pipeline import _team_budget
from app.services.policy_service import POLICY_BLOCK_STATUS, policy_service, policy_store
from app.services.rate_limiter import rate_limiter_service
from app.services.realtime_relay import Disconnected, Hooks, relay
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Proxy"])

KEY_SUBPROTOCOL = "openai-insecure-api-key."
SERVED_SUBPROTOCOL = "realtime"
PROVIDER = "openai"


def credential_of(ws: WebSocket) -> str | None:
	"""The opai_ key from the Authorization header or a subprotocol, or None."""
	header = ws.headers.get("authorization", "")
	scheme, _, value = header.partition(" ")
	if scheme.lower() == "bearer" and value.strip():
		return value.strip()
	for offered in (p.strip() for p in ws.headers.get("sec-websocket-protocol", "").split(",")):
		if offered.startswith(KEY_SUBPROTOCOL):
			return offered[len(KEY_SUBPROTOCOL):] or None
	return None


class ClientSocket:
	def __init__(self, ws: WebSocket) -> None:
		self._ws = ws

	async def receive(self) -> str | bytes:
		message = await self._ws.receive()
		if message["type"] == "websocket.disconnect":
			raise Disconnected()
		if message.get("text") is not None:
			return message["text"]
		return message.get("bytes") or b""

	async def send_text(self, data: str | bytes) -> None:
		try:
			await (self._ws.send_text(data) if isinstance(data, str) else self._ws.send_bytes(data))
		except (WebSocketDisconnect, RuntimeError):
			raise Disconnected() from None

	async def close(self, code: int, reason: str = "") -> None:
		await self._ws.close(code=code, reason=reason[:120])


class UpstreamSocket:
	def __init__(self, connection: Any) -> None:
		self._c = connection

	async def recv(self) -> str | bytes:
		from websockets.exceptions import ConnectionClosed

		try:
			return await self._c.recv()
		except ConnectionClosed:
			raise Disconnected() from None

	async def send(self, data: str | bytes) -> None:
		from websockets.exceptions import ConnectionClosed

		try:
			await self._c.send(data)
		except ConnectionClosed:
			raise Disconnected() from None

	async def close(self, code: int, reason: str = "") -> None:
		await self._c.close(code, reason[:120])


async def open_upstream(model_name: str, api_key: str) -> Any:
	"""Connects to the provider. A seam: tests point it at a local server."""
	from urllib.parse import quote

	from websockets.asyncio.client import connect

	return await connect(
		f"{settings.REALTIME_UPSTREAM_URL}?model={quote(model_name, safe='')}",
		additional_headers={"Authorization": f"Bearer {api_key}", "OpenAI-Beta": "realtime=v1"},
		max_size=settings.REALTIME_MAX_MESSAGE_BYTES * 4, open_timeout=10, ping_interval=20,
	)


async def _refuse(ws: WebSocket, code: int, reason: str) -> None:
	try:
		await ws.close(code=code, reason=reason[:120])
	except RuntimeError:
		pass


@router.websocket("/v1/realtime")
async def realtime(ws: WebSocket) -> None:
	credential = credential_of(ws)
	redis = ws.app.state.redis
	if not credential or not credential.startswith("opai_"):
		await ws.close(code=1008)  # before accept: the client sees an HTTP 403
		return
	async with AsyncSessionLocal() as db:
		try:
			api_key = await validate_api_key(db=db, redis=redis, api_key=credential)
		except HTTPException:
			await ws.close(code=1008)
			return
		user, org_id = api_key.user, api_key.org_id
		user_id, api_key_id = user.id, api_key.id
		user_budget = getattr(user, "budget_daily_usd", None)
		request_like = SimpleNamespace(headers=ws.headers)  # the HTTP header parsers read .headers only
		model = ws.query_params.get("model", "")
		subprotocol = SERVED_SUBPROTOCOL if SERVED_SUBPROTOCOL in ws.headers.get("sec-websocket-protocol", "") else None
		await ws.accept(subprotocol=subprotocol)

		if not settings.REALTIME_ENABLED:
			return await _refuse(ws, 1008, "realtime_disabled")
		try:
			provider, model_name = ls.split_model(model)
		except HTTPException:
			return await _refuse(ws, 1008, "model_must_be_provider_slash_name")
		if provider != PROVIDER:
			return await _refuse(ws, 1008, "only_openai_is_supported")

		try:
			team_id = getattr(api_key, "team_id", None) or ls._parse_team_id(request_like)
			labels = ls._parse_labels(request_like)
			team_budget = await _team_budget(db, user, team_id) if team_id is not None else None
		except HTTPException as exc:
			return await _refuse(ws, 1008, f"team_or_labels_refused:{exc.status_code}")

		request_id = uuid.uuid4()
		started = time.perf_counter()
		state: dict[str, Any] = {"config": await policy_store.load(org_id, db, redis), "checked": time.monotonic(), "classification": None}
		config = state["config"]

		def log(**fields: Any) -> Any:
			return ls.log_request(
				redis=redis, request_id=fields.pop("request_id", request_id), org_id=org_id, user_id=user_id, api_key_id=api_key_id,
				model=model, provider=provider, ttft_ms=None, labels=labels, team_id=team_id, **fields,
			)

		def metadata(extra: dict | None = None) -> dict:
			out = {"modality": "realtime", **(extra or {})}
			if state["classification"] is not None:
				out["data_class"] = state["classification"].as_metadata()
			return out

		async def refuse_and_log(reason: str, status: int = POLICY_BLOCK_STATUS) -> None:
			await log(prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0"), latency_ms=0, status_code=status, error_message=reason, request_metadata=metadata())
			await _refuse(ws, 1008, reason)

		if config.response_guardrails_enabled and config.enforcement_mode.lower().strip() == "enforce":
			return await refuse_and_log("response_guardrails_not_supported_in_realtime")
		decision = await policy_service.evaluate_text_request(model, "", config)
		# Audio cannot be read, so the session is classified as uninspected, which the org's class map raises like any other "could not scan".
		state["classification"] = await classify_text(None, config, None)
		if not decision.allowed:
			return await refuse_and_log(f"policy_blocked:{decision.reason_code}")
		routing = None
		if config.routing_mode != "off":
			candidates, region = await ls.llm_service.routing_inputs(db, org_id)
			routing = ls.route_decision(candidates, region, config, state["classification"].data_class, model)
			if routing.blocked:
				return await refuse_and_log("policy_blocked:no_authorized_model")

		async def admit() -> str | None:
			ok, _headers, limit_type, detail, _retry = await rate_limiter_service.check_limits(
				redis=redis, org_id=str(org_id), user_id=str(user_id), request_tokens_estimate=1,
				max_rpm=settings.DEFAULT_RATE_LIMIT_RPM, max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
				max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)), user_daily_budget_usd=user_budget,
				team_id=str(team_id) if team_id else None, team_budget_monthly_usd=team_budget, model=model, policy_config=state["config"],
			)
			return None if ok else f"rate_limited:{limit_type}"

		blocked = await admit()
		if blocked:
			return await refuse_and_log(blocked, 429)

		try:
			keys = await ls.llm_service._select_provider_keys(
				db, org_id, provider, model=model_name, redis=redis, max_attempts=None,
				only_key_id=routing.key_id if routing is not None and routing.mode == "enforce" else None,
			)
		except HTTPException as exc:
			return await refuse_and_log(f"no_provider_key:{exc.status_code}", 503)
	# The database is not needed from here on: a session can last an hour.

	own_endpoint = [k for k in keys if k.api_base is None]
	if not own_endpoint:
		return await refuse_and_log("realtime_needs_the_providers_own_endpoint", 503)

	counter = f"rt:sessions:{org_id}"
	if await redis.incr(counter) > settings.REALTIME_MAX_SESSIONS_PER_ORG:
		await redis.decr(counter)
		return await refuse_and_log("too_many_realtime_sessions", 429)
	await redis.expire(counter, settings.REALTIME_MAX_SESSION_SECONDS * 2)
	upstream = None
	chosen = None
	try:
		for candidate in own_endpoint:
			try:
				upstream = await open_upstream(model_name, candidate.api_key)
				chosen = candidate
				break
			except Exception as exc:  # noqa: BLE001  (the provider refused or is down: try the next key; the message may hold a key)
				logger.warning("realtime upstream connect failed: %s", type(exc).__name__)
		if upstream is None:
			return await refuse_and_log("provider_unavailable", 502)

		async def scan(text: str) -> str | None:
			result = await policy_service.evaluate_text_request(model, text, state["config"])
			if result.allowed:
				return None
			await log(prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0"), latency_ms=0, status_code=POLICY_BLOCK_STATUS,
				error_message=f"policy_blocked:{result.reason_code}", request_metadata=metadata(result.as_metadata()), request_id=uuid.uuid4())
			return str(result.reason_code or "policy")

		async def record(response: dict) -> None:
			usage = response.get("usage")
			counts = realtime_pricing.tokens_of(usage)
			extra: dict = {"realtime_response_id": str(response.get("id", ""))[:64], "realtime_status": str(response.get("status", ""))[:32]}
			try:
				cost = realtime_pricing.cost_usd(model, usage)
			except realtime_pricing.Unpriced as exc:
				logger.warning("Could not price realtime response for %s: %s", model, exc)
				cost, extra["cost_estimated"] = Decimal(str(settings.UNPRICED_CALL_COST_USD)), True
			await log(
				request_id=uuid.uuid4(), prompt_tokens=counts[0] if counts else 0, completion_tokens=counts[1] if counts else 0, cost_usd=cost,
				latency_ms=int((time.perf_counter() - started) * 1000), status_code=200, provider_key_id=chosen.key_id, request_metadata=metadata(extra),
			)

		async def still_valid() -> bool:
			async with AsyncSessionLocal() as check_db:
				try:
					await validate_api_key(db=check_db, redis=redis, api_key=credential)
				except HTTPException:
					return False
				state["config"] = await policy_store.load(org_id, check_db, redis)
			cfg = state["config"]
			if cfg.response_guardrails_enabled and cfg.enforcement_mode.lower().strip() == "enforce":
				return False
			return (await policy_service.evaluate_text_request(model, "", cfg)).allowed

		hooks = Hooks(scan=scan, admit_response=admit, record_response=record, still_valid=still_valid)
		code, reason = await relay(
			ClientSocket(ws), UpstreamSocket(upstream), hooks, model_name=model_name, max_message_bytes=settings.REALTIME_MAX_MESSAGE_BYTES,
			max_seconds=settings.REALTIME_MAX_SESSION_SECONDS, check_every=settings.REALTIME_CHECK_SECONDS,
		)
		logger.info("realtime session %s ended: %s %s", request_id, code, reason)
	finally:
		await redis.decr(counter)
		if upstream is not None:
			try:
				await upstream.close()
			except Exception:  # noqa: BLE001
				pass
