"""Organization schemas for management APIs."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DataRegion = Literal["us", "eu", "ap"]


class OrganizationResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	name: str
	slug: str
	plan: str
	settings: dict[str, Any]
	budget_monthly_usd: Decimal | None
	is_active: bool
	data_region: str | None
	created_at: datetime
	stripe_customer_id: str | None = None
	stripe_subscription_id: str | None = None
	stripe_subscription_status: str | None = None
	# Populated for usage-metered plans (see ``METERED_INCLUDED_TOKENS_MONTHLY``).
	included_tokens_monthly: int | None = None


class OrganizationUpdateRequest(BaseModel):
	name: str | None = Field(default=None, min_length=1, max_length=255)
	plan: str | None = Field(default=None, min_length=1, max_length=50)
	settings: dict[str, Any] | None = None
	budget_monthly_usd: Decimal | None = Field(default=None, ge=0)
	is_active: bool | None = None
	data_region: _DataRegion | None = Field(default=None, description="Data region: us, eu, or ap")

	@field_validator("data_region", mode="before")
	@classmethod
	def _normalize_data_region(cls, v: str | None) -> str | None:
		if v is None:
			return None
		return v.strip().lower() if isinstance(v, str) else v
