"""Pydantic schemas for webhook configuration."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.services.webhook_service import _is_safe_url


class WebhookConfigRequest(BaseModel):
    url: str
    secret: str = ""
    events: list[str] = ["policy.violation", "budget.alert"]
    enabled: bool = True

    @field_validator("events")
    @classmethod
    def valid_events(cls, v: list[str]) -> list[str]:
        allowed = {"policy.violation", "budget.alert"}
        for event in v:
            if event not in allowed:
                raise ValueError(f"Unknown event type: {event}. Allowed: {allowed}")
        return v

    @field_validator("url")
    @classmethod
    def url_must_be_safe_https(cls, v: str) -> str:
        if not _is_safe_url(v):
            raise ValueError(
                "Webhook URL must be https:// and must not resolve to private/local addresses"
            )
        return v


class WebhookConfigResponse(BaseModel):
    url: str
    events: list[str]
    enabled: bool


class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    url: str
    status: str
    http_status: int | None
    attempt_count: int
    last_attempted_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryDetailResponse(WebhookDeliveryResponse):
    payload: dict
