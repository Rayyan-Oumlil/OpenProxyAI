from __future__ import annotations


class OpenProxyError(Exception):
    """Base exception for all OpenProxy SDK errors."""
    status_code: int | None = None

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class AuthError(OpenProxyError):
    """HTTP 401 — invalid or missing API key."""


class PolicyViolationError(OpenProxyError):
    """HTTP 403 — request blocked by policy."""

    def __init__(self, message: str, reason_code: str | None = None, triggered_rules: list[str] | None = None, **kwargs):
        super().__init__(message, status_code=403, **kwargs)
        self.reason_code = reason_code
        self.triggered_rules = triggered_rules or []


class RateLimitError(OpenProxyError):
    """HTTP 429 — rate limit exceeded."""

    def __init__(self, message: str, limit_type: str | None = None, retry_after: int | None = None, **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.limit_type = limit_type
        self.retry_after = retry_after


class BudgetExceededError(RateLimitError):
    """HTTP 429 budget type — daily budget exhausted."""


class ProviderError(OpenProxyError):
    """HTTP 502/504 — upstream provider error."""

    def __init__(self, message: str, provider: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.provider = provider


class APIError(OpenProxyError):
    """Generic API error for unexpected status codes."""
