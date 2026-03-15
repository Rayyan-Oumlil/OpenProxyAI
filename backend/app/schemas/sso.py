"""Pydantic schemas for SSO connection management."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class SSOConnectionCreateRequest(BaseModel):
    provider_name: str
    issuer_url: str  # use str not HttpUrl so we can strip trailing slash
    client_id: str
    client_secret: str
    domain_hint: str | None = None


class SSOConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    provider_name: str
    issuer_url: str
    client_id: str
    domain_hint: str | None
    is_active: bool
