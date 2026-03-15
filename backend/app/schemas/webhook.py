"""Pydantic schemas for webhook configuration."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


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
    def url_must_be_https_or_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v


class WebhookConfigResponse(BaseModel):
    url: str
    events: list[str]
    enabled: bool
    # secret is NEVER returned
