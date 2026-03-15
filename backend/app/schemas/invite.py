"""Invite schemas — create, response, accept."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InviteCreateRequest(BaseModel):
    email: EmailStr
    role: Literal["admin", "developer", "viewer"] = "developer"


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    role: str
    invited_by: uuid.UUID | None
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InviteCreatedResponse(InviteResponse):
    invite_url: str


class AcceptInviteRequest(BaseModel):
    token: str
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
