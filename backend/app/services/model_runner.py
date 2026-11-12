"""Calling a model from inside the gateway: eval runs, judge calls and the playground.

Not a client request, but held to the same rules as one:

- The org's policy runs first (keywords, PII, model allowlist). A block is a *refusal*, nothing reaches a provider.
- With routing on, the prompt is classified and only a model authorized for its data class may serve it, through its
  registry key and no other (the same decision a client request gets).
- The key and custom endpoint are chosen by the same code chat uses, so key rotation, regions and the connection guard
  apply.
- Every call is written to the audit log with its tokens and cost, tagged with its ``source``, so it shows up in
  spend and in the request logs like any other traffic.

Failures come back as an outcome, never an exception, so one bad item cannot abort a whole run.

A call has two phases so that callers can run many at once. ``plan_call`` decides (policy, classification, routing, key) and
uses the database session, so plans are made one after another. ``execute_plan`` makes the provider call, prices it and
audit-logs it, and uses no session, so plans can be executed concurrently. ``run_prompt`` is the two together for a caller
that makes one call at a time.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
import litellm
from litellm import acompletion
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.chat import ChatCompletionRequest
from app.services.audit_logger import log_request
from app.services.classification_service import Classification, classify_chat_request
from app.services.cost_tracker import cost_tracker_service
from app.services.llm_service import ProviderKeyCandidate, llm_service, route_decision, split_model, with_endpoint
from app.services.policy_service import POLICY_BLOCK_STATUS, PolicyConfig, policy_service
from app.services.provider_client import ProviderEndpoint
from app.services.routing_service import Candidate

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60
KEY_UNAVAILABLE_STATUS = 503  # what the audit log records when no provider key could be chosen

RoutingInputs = tuple[list[Candidate], str]  # the registry and the org's region, as llm_service.routing_inputs returns them


@dataclass(frozen=True)
class RunOutcome:
	content: str = ""
	prompt_tokens: int = 0
	completion_tokens: int = 0
	cost_usd: Decimal = Decimal("0")
	latency_ms: int = 0
	error: str | None = None
	refused: bool = False  # policy or routing said no; nothing was sent to a provider


@dataclass(frozen=True)
class CallPlan:
	"""A call that has been authorized and has its key, ready to execute. Holds no database session."""

	request_id: uuid.UUID
	model: str
	provider: str
	messages: list[dict[str, Any]]
	candidate: ProviderKeyCandidate
	metadata: dict[str, Any]
	temperature: float | None
	max_tokens: int | None
	timeout: int
	started: float = field(default_factory=time.perf_counter)


def _detail(exc: HTTPException) -> str:
	return str(exc.detail.get("detail") if isinstance(exc.detail, dict) else exc.detail)


def _elapsed_ms(started: float) -> int:
	return int((time.perf_counter() - started) * 1000)


async def _log(redis: Redis | None, request_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID, model: str, provider: str,
               metadata: dict, started: float, *, status_code: int, prompt_tokens: int = 0, completion_tokens: int = 0,
               cost: Decimal = Decimal("0"), error: str | None = None) -> None:
	"""Audit-log one call. A logging failure is recorded and swallowed: it must not lose an answer already paid for."""
	try:
		await log_request(
			redis=redis, request_id=request_id, org_id=org_id, user_id=user_id, api_key_id=None, model=model, provider=provider,
			prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost,
			latency_ms=_elapsed_ms(started), ttft_ms=None, status_code=status_code,
			error_message=error, request_metadata=metadata, labels=None,
		)
	except Exception:
		logger.exception("could not audit-log an internal model call (request %s)", request_id)


async def plan_call(
	*,
	db: AsyncSession,
	redis: Redis | None,
	org_id: uuid.UUID,
	user_id: uuid.UUID,
	model: str,
	messages: list[dict[str, Any]],
	policy_config: PolicyConfig,
	source: str,
	extra_metadata: dict[str, Any] | None = None,
	temperature: float | None = None,
	max_tokens: int | None = None,
	timeout: int = TIMEOUT_SECONDS,
	check_policy: bool = True,
	classification: Classification | None = None,
	routing_inputs: RoutingInputs | None = None,
) -> CallPlan | RunOutcome:
	"""Authorize one call and choose its key. Returns a ``CallPlan`` to execute, or the ``RunOutcome`` that ends it.

	Uses ``db``, so call it for one model at a time. ``check_policy=False`` is for a caller that has already applied the
	org's policy to the whole request (the playground blocks the request before planning any model).
	``classification`` and ``routing_inputs`` let a caller that plans several models for one prompt classify and load the
	registry once instead of once per model.
	"""
	started = time.perf_counter()
	request_id = uuid.uuid4()
	try:
		provider, model_name = split_model(model)
		request = ChatCompletionRequest(model=model, messages=messages)
	except HTTPException as exc:
		return RunOutcome(error=_detail(exc))
	except ValidationError as exc:
		return RunOutcome(error=f"invalid messages: {exc.errors()[0]['msg']}")

	metadata: dict[str, Any] = {"source": source, **(extra_metadata or {})}
	try:
		if check_policy:
			decision = await policy_service.evaluate_chat_request(request, policy_config)
			if not decision.allowed:
				reason = decision.detail or "Blocked by policy."
				await _log(redis, request_id, org_id, user_id, model, provider, {**metadata, "policy": {"action": "block", "reason_code": decision.reason_code}},
				           started, status_code=POLICY_BLOCK_STATUS, error=reason)
				return RunOutcome(error=reason, refused=True, latency_ms=_elapsed_ms(started))

		if classification is None:
			classification = await classify_chat_request(ChatCompletionRequest.model_construct(model="", messages=request.messages), policy_config, None)
		metadata["data_class"] = classification.as_metadata()
		routing, only_key_id = None, None
		if policy_config.routing_mode != "off":
			candidates, region = routing_inputs if routing_inputs is not None else await llm_service.routing_inputs(db, org_id, policy_config)
			routing = route_decision(candidates, region, policy_config, classification.data_class, model)
		if routing is not None:
			metadata["routing"] = routing.as_metadata()
			if routing.blocked:
				reason = f"Not authorized for {classification.data_class} data: {routing.reason}"
				await _log(redis, request_id, org_id, user_id, model, provider, metadata, started, status_code=POLICY_BLOCK_STATUS, error=reason)
				return RunOutcome(error=reason, refused=True, latency_ms=_elapsed_ms(started))
			only_key_id = routing.key_id if routing.mode == "enforce" else None

		try:
			[candidate, *_] = await llm_service._select_provider_keys(db, org_id, provider, model=model_name, max_attempts=0, only_key_id=only_key_id)
		except HTTPException as exc:
			reason = _detail(exc)
			await _log(redis, request_id, org_id, user_id, model, provider, metadata, started, status_code=KEY_UNAVAILABLE_STATUS, error=reason)
			return RunOutcome(error=reason, latency_ms=_elapsed_ms(started))
		return CallPlan(
			request_id=request_id, model=model, provider=provider, messages=messages, candidate=candidate, metadata=metadata,
			temperature=temperature, max_tokens=max_tokens, timeout=timeout, started=started,
		)
	except HTTPException as exc:
		return RunOutcome(error=_detail(exc), latency_ms=_elapsed_ms(started))
	except Exception as exc:
		logger.exception("planning a model call failed (request %s)", request_id)
		return RunOutcome(error=str(exc), latency_ms=_elapsed_ms(started))


def _call_kwargs(plan: CallPlan) -> dict[str, Any]:
	kwargs: dict[str, Any] = {
		"model": plan.model, "messages": plan.messages, "api_key": plan.candidate.api_key, "timeout": plan.timeout, "request_timeout": plan.timeout,
	}
	endpoint = ProviderEndpoint(plan.candidate.api_base, plan.candidate.is_internal) if plan.candidate.api_base else None
	kwargs = with_endpoint(kwargs, plan.candidate.api_key, endpoint)
	if plan.temperature is not None:
		kwargs["temperature"] = plan.temperature
	if plan.max_tokens is not None:
		kwargs["max_tokens"] = plan.max_tokens
	return kwargs


def _estimate_prompt_tokens(messages: list[dict[str, Any]]) -> int:
	return max(1, sum(len(str(m.get("content", ""))) for m in messages) // 4)


def _stream_cost(plan: CallPlan, chunks: list[Any], finished: bool, prompt_tokens: int, completion_tokens: int) -> Decimal:
	"""Price a stream that reached the provider, however it ended. The provider charges for what it generated even when the caller
	left or the stream broke, so an abandoned stream is priced from its tokens, never at zero (that would let spend go uncounted by
	disconnecting). If even that cannot be priced, charge the flat per-call fallback."""
	if finished and chunks:
		try:
			return cost_tracker_service.calculate_cost_usd(litellm.stream_chunk_builder(chunks, messages=plan.messages))
		except Exception:  # noqa: BLE001
			pass
	try:
		prompt_cost, completion_cost = litellm.cost_per_token(model=plan.model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
		return Decimal(str(prompt_cost + completion_cost)).quantize(Decimal("0.000001"))
	except Exception:  # noqa: BLE001
		logger.warning("could not price a stream to %s; charging the flat fallback", plan.model)
		return Decimal(str(settings.UNPRICED_CALL_COST_USD))


CLIENT_GONE_STATUS = 499  # what the audit log records when the caller disconnected mid-stream


async def stream_plan(plan: CallPlan, *, redis: Redis | None, org_id: uuid.UUID, user_id: uuid.UUID):
	"""Make the provider call as a stream. Yields each piece of text (``str``) as it arrives, then one final ``RunOutcome``.

	The call is audit-logged exactly once, whichever way it ends: complete (200, priced), failed (502), or abandoned by the caller
	(499, with the text delivered so far estimated, because the provider charged for it). Never raises.
	"""
	pieces: list[str] = []
	chunks: list[Any] = []
	status, error, finished = 502, None, False
	try:
		stream = await acompletion(**_call_kwargs(plan), stream=True, stream_options={"include_usage": True})
		async for chunk in stream:
			chunks.append(chunk)
			choices = getattr(chunk, "choices", None) or []
			delta = getattr(getattr(choices[0], "delta", None), "content", None) if choices else None
			if delta:
				pieces.append(delta)
				yield delta
		status, finished = 200, True
	except (GeneratorExit, asyncio.CancelledError):
		status, error = CLIENT_GONE_STATUS, "the caller disconnected before the answer finished"
		raise
	except Exception as exc:
		error = str(exc)
	finally:
		text = "".join(pieces)
		usage = next((getattr(c, "usage", None) for c in reversed(chunks) if getattr(c, "usage", None)), None)
		prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) or _estimate_prompt_tokens(plan.messages)
		completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) or (len(text) // 4 if text else 0)
		cost = _stream_cost(plan, chunks, finished, prompt_tokens, completion_tokens)
		await asyncio.shield(_log(
			redis, plan.request_id, org_id, user_id, plan.model, plan.provider, plan.metadata, plan.started, status_code=status,
			prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost=cost, error=error,
		))
	if finished:
		yield RunOutcome(content=text, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost, latency_ms=_elapsed_ms(plan.started))
	else:
		yield RunOutcome(error=error or "the call failed", latency_ms=_elapsed_ms(plan.started))


async def execute_plan(plan: CallPlan, *, redis: Redis | None, org_id: uuid.UUID, user_id: uuid.UUID) -> RunOutcome:
	"""Make the provider call, price it and audit-log it. Uses no database session, so plans can run concurrently. Never raises."""
	try:
		response = await acompletion(**_call_kwargs(plan))
		usage = getattr(response, "usage", None)
		prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
		completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
		cost = cost_tracker_service.calculate_cost_usd(response)
		content = (getattr(response.choices[0].message, "content", "") or "") if response.choices else ""
		await _log(redis, plan.request_id, org_id, user_id, plan.model, plan.provider, plan.metadata, plan.started, status_code=200,
		           prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost=cost)
		return RunOutcome(content=content, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost, latency_ms=_elapsed_ms(plan.started))
	except Exception as exc:
		await _log(redis, plan.request_id, org_id, user_id, plan.model, plan.provider, plan.metadata, plan.started, status_code=502, error=str(exc))
		return RunOutcome(error=str(exc), latency_ms=_elapsed_ms(plan.started))


async def run_prompt(
	*,
	db: AsyncSession,
	redis: Redis | None,
	org_id: uuid.UUID,
	user_id: uuid.UUID,
	model: str,
	messages: list[dict[str, Any]],
	policy_config: PolicyConfig,
	source: str,
	extra_metadata: dict[str, Any] | None = None,
	temperature: float | None = None,
	max_tokens: int | None = None,
) -> RunOutcome:
	"""One model call with the gateway's policy, routing and metering. Never raises."""
	planned = await plan_call(
		db=db, redis=redis, org_id=org_id, user_id=user_id, model=model, messages=messages, policy_config=policy_config, source=source,
		extra_metadata=extra_metadata, temperature=temperature, max_tokens=max_tokens,
	)
	if isinstance(planned, RunOutcome):
		return planned
	return await execute_plan(planned, redis=redis, org_id=org_id, user_id=user_id)
