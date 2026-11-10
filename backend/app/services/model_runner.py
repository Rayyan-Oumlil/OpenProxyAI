"""Calling a model from inside the gateway: eval runs and judge calls (Phase 3, slice 4).

Not a client request, but held to the same rules as one:

- The org's policy runs first (keywords, PII, model allowlist). A block is a *refusal*, nothing reaches a provider.
- With routing on, the prompt is classified and only a model authorized for its data class may serve it, through its
  registry key and no other (the same decision a client request gets).
- The key and custom endpoint are chosen by the same code chat uses, so key rotation, regions and the connection guard
  apply.
- Every call is written to the audit log with its tokens and cost, tagged with its ``source``, so an eval run shows up in
  spend and in the request logs like any other traffic.

Failures come back as an outcome, never an exception, so one bad item cannot abort a whole run.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from litellm import acompletion
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatCompletionRequest
from app.services.audit_logger import log_request
from app.services.classification_service import classify_chat_request
from app.services.cost_tracker import cost_tracker_service
from app.services.llm_service import llm_service, route_decision, split_model, with_endpoint
from app.services.policy_service import POLICY_BLOCK_STATUS, PolicyConfig, policy_service
from app.services.provider_client import ProviderEndpoint

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class RunOutcome:
	content: str = ""
	prompt_tokens: int = 0
	completion_tokens: int = 0
	cost_usd: Decimal = Decimal("0")
	latency_ms: int = 0
	error: str | None = None
	refused: bool = False  # policy or routing said no; nothing was sent to a provider


def _detail(exc: HTTPException) -> str:
	return str(exc.detail.get("detail") if isinstance(exc.detail, dict) else exc.detail)


async def _log(redis: Redis | None, request_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID, model: str, provider: str,
               metadata: dict, started: float, *, status_code: int, prompt_tokens: int = 0, completion_tokens: int = 0,
               cost: Decimal = Decimal("0"), error: str | None = None) -> None:
	"""Audit-log one call. A logging failure is recorded and swallowed: it must not lose an answer already paid for."""
	try:
		await log_request(
			redis=redis, request_id=request_id, org_id=org_id, user_id=user_id, api_key_id=None, model=model, provider=provider,
			prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost,
			latency_ms=int((time.perf_counter() - started) * 1000), ttft_ms=None, status_code=status_code,
			error_message=error, request_metadata=metadata, labels=None,
		)
	except Exception:
		logger.exception("could not audit-log an internal model call (request %s)", request_id)


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
		decision = await policy_service.evaluate_chat_request(request, policy_config)
		if not decision.allowed:
			reason = decision.detail or "Blocked by policy."
			await _log(redis, request_id, org_id, user_id, model, provider, {**metadata, "policy": {"action": "block", "reason_code": decision.reason_code}},
			           started, status_code=POLICY_BLOCK_STATUS, error=reason)
			return RunOutcome(error=reason, refused=True, latency_ms=int((time.perf_counter() - started) * 1000))

		classification = await classify_chat_request(ChatCompletionRequest.model_construct(model="", messages=request.messages), policy_config, None)
		metadata["data_class"] = classification.as_metadata()
		routing, only_key_id = None, None
		if policy_config.routing_mode != "off":
			candidates, region = await llm_service.routing_inputs(db, org_id)
			routing = route_decision(candidates, region, policy_config, classification.data_class, model)
		if routing is not None:
			metadata["routing"] = routing.as_metadata()
			if routing.blocked:
				reason = f"Not authorized for {classification.data_class} data: {routing.reason}"
				await _log(redis, request_id, org_id, user_id, model, provider, metadata, started, status_code=POLICY_BLOCK_STATUS, error=reason)
				return RunOutcome(error=reason, refused=True, latency_ms=int((time.perf_counter() - started) * 1000))
			only_key_id = routing.key_id if routing.mode == "enforce" else None

		[candidate, *_] = await llm_service._select_provider_keys(db, org_id, provider, model=model_name, max_attempts=0, only_key_id=only_key_id)
		kwargs: dict[str, Any] = {"model": model, "messages": messages, "api_key": candidate.api_key, "timeout": TIMEOUT_SECONDS, "request_timeout": TIMEOUT_SECONDS}
		kwargs = with_endpoint(kwargs, candidate.api_key, ProviderEndpoint(candidate.api_base, candidate.is_internal) if candidate.api_base else None)
		if temperature is not None:
			kwargs["temperature"] = temperature
		if max_tokens is not None:
			kwargs["max_tokens"] = max_tokens

		response = await acompletion(**kwargs)
		usage = getattr(response, "usage", None)
		prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
		completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
		cost = cost_tracker_service.calculate_cost_usd(response)
		content = (getattr(response.choices[0].message, "content", "") or "") if response.choices else ""
		await _log(redis, request_id, org_id, user_id, model, provider, metadata, started, status_code=200,
		           prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost=cost)
		return RunOutcome(content=content, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost,
		                  latency_ms=int((time.perf_counter() - started) * 1000))
	except HTTPException as exc:
		return RunOutcome(error=_detail(exc), latency_ms=int((time.perf_counter() - started) * 1000))
	except Exception as exc:
		await _log(redis, request_id, org_id, user_id, model, provider, metadata, started, status_code=502, error=str(exc))
		return RunOutcome(error=str(exc), latency_ms=int((time.perf_counter() - started) * 1000))
