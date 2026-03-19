"""Team schemas — CRUD request/response for departmental cost attribution."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    budget_monthly_usd: Decimal | None = Field(default=None, ge=0)


class TeamUpdateRequest(BaseModel):
    """Partial update — only provided fields are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    budget_monthly_usd: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def name_not_null(self) -> "TeamUpdateRequest":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be set to null")
        return self


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    budget_monthly_usd: Decimal | None
    created_at: datetime
    member_count: int = 0


class TeamDetailResponse(TeamResponse):
    """Team with member list for detail view."""

    members: list[TeamMemberResponse] = Field(default_factory=list)
