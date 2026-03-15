from __future__ import annotations
import time
import json
from typing import Any
import httpx

from ._exceptions import (
    AuthError,
    PolicyViolationError,
    RateLimitError,
    BudgetExceededError,
    ProviderError,
    APIError,
)
from ._streaming import _extract_gateway_meta

DEFAULT_BASE_URL = "https://api.openproxyai.com"
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 3


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    try:
        body = response.json()
    except Exception:
        body = {"detail": response.text}

    error = body.get("error", "")
    detail = body.get("detail", str(response.status_code))

    if response.status_code == 401:
        raise AuthError(detail, status_code=401, response=body)
    if response.status_code == 403:
        if error == "policy_violation":
            raise PolicyViolationError(
                detail,
                reason_code=body.get("reason_code"),
                triggered_rules=body.get("triggered_rules", []),
                response=body,
            )
        raise AuthError(detail, status_code=403, response=body)
    if response.status_code == 429:
        limit_type = body.get("limit_type", "")
        retry_after = body.get("retry_after")
        if "budget" in limit_type:
            raise BudgetExceededError(detail, limit_type=limit_type, retry_after=retry_after, response=body)
        raise RateLimitError(detail, limit_type=limit_type, retry_after=retry_after, response=body)
    if response.status_code in (502, 504):
        provider = response.headers.get("x-openproxyai-provider")
        raise ProviderError(detail, provider=provider, status_code=response.status_code, response=body)
    raise APIError(detail, status_code=response.status_code, response=body)


def _should_retry(exc: Exception, attempt: int) -> bool:
    if attempt >= MAX_RETRIES:
        return False
    if isinstance(exc, (RateLimitError, ProviderError)):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    return False


def _backoff(attempt: int) -> float:
    return min(2 ** attempt * 0.5, 8.0)
