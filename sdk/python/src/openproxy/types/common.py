from __future__ import annotations
from dataclasses import dataclass, field
from typing import Generic, TypeVar
T = TypeVar("T")

@dataclass
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

@dataclass
class GatewayMeta:
    request_id: str | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    provider: str | None = None
    model: str | None = None
    policy_action: str | None = None
    policy_reason: str | None = None
    ttft_ms: int | None = None
    cache: str | None = None
