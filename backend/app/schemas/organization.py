"""Organization schemas for management APIs."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrganizationResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	name: str
	slug: str
	plan: str
	settings: dict[str, Any]
	budget_monthly_usd: Decimal | None
	is_active: bool
	created_at: datetime


class OrganizationUpdateRequest(BaseModel):
	name: str | None = Field(default=None, min_length=1, max_length=255)
	plan: str | None = Field(default=None, min_length=1, max_length=50)
	settings: dict[str, Any] | None = None
	budget_monthly_usd: Decimal | None = Field(default=None, ge=0)
	is_active: bool | None = None
