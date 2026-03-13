"""User schemas for management APIs."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	org_id: uuid.UUID
	email: str
	name: str | None
	role: str
	budget_daily_usd: Decimal | None
	budget_monthly_usd: Decimal | None
	is_active: bool
	created_at: datetime


class UserUpdateRequest(BaseModel):
	name: str | None = Field(default=None, min_length=1, max_length=255)
	role: Literal["admin", "developer", "viewer"] | None = None
	budget_daily_usd: Decimal | None = Field(default=None, ge=0)
	budget_monthly_usd: Decimal | None = Field(default=None, ge=0)
	is_active: bool | None = None
