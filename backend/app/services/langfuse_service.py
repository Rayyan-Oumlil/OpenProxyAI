"""Optional Langfuse LLM tracing -- fire-and-forget, no-ops when not configured.

Langfuse v4 API:
  client.start_observation(name=..., as_type='generation', trace_context={trace_id: ...}, ...)
  observation.end()
  client.flush()
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_client: Any = None
_initialized = False


def _get_client() -> Any:
    """Lazily initialize the Langfuse client. Returns None if not configured."""
    global _client, _initialized
    if _initialized:
        return _client
    _initialized = True
    if settings.AIRGAP_MODE:
        return None
    if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
        return None
    try:
        from langfuse import Langfuse

        _client = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Langfuse tracing enabled (host=%s)", settings.LANGFUSE_HOST)
    except Exception:
        logger.exception("Failed to initialize Langfuse client -- tracing disabled")
    return _client


def is_enabled() -> bool:
    """Return True if Langfuse is configured and the client initialized successfully."""
    return _get_client() is not None


async def send_trace(
    *,
    request_id: str,
    org_id: str,
    user_id: str,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    latency_ms: int | None,
    ttft_ms: int | None,
    status_code: int,
    policy_action: str | None,
    error_message: str | None,
) -> None:
    """Send a trace to Langfuse (v4 API). Swallows all exceptions."""
    client = _get_client()
    if client is None:
        return
    try:
        from langfuse.types import TraceContext

        # Langfuse v4 requires a 32-char lowercase hex trace_id (no dashes).
        trace_ctx: TraceContext = {"trace_id": request_id.replace("-", "")}
        observation = client.start_observation(
            trace_context=trace_ctx,
            name="openproxy.proxy_request",
            as_type="generation",
            model=model,
            usage_details={
                "input": prompt_tokens,
                "output": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            },
            cost_details={"total": cost_usd},
            metadata={
                "org_id": org_id,
                "user_id": user_id,
                "provider": provider,
                "policy_action": policy_action or "allow",
                "status_code": status_code,
                "latency_ms": latency_ms,
                "ttft_ms": ttft_ms,
                "error": error_message,
            },
            level="ERROR" if error_message else "DEFAULT",
        )
        observation.end()
        client.flush()
    except Exception:
        logger.exception(
            "Failed to send trace to Langfuse (request_id=%s)", request_id
        )
