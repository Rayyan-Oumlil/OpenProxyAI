"""Schemas for the model registry: /api/v1/model-registry."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.provider_key import Region
from app.services.data_class import DataClass

ModelId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:@/-]+$", max_length=200)]
Capability = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,39}$")]
Rating = Literal["low", "medium", "high"]


def _unique(values: list) -> list:
	if len(set(values)) != len(values):
		raise ValueError("values must be unique")
	return values


class ModelRegistryCreate(BaseModel):
	model_id: ModelId = Field(description="provider/name exactly as clients send it, e.g. openai/gpt-4o")
	provider_key_id: UUID | None = Field(default=None, description="The provider key that serves this model (its api_base is the endpoint)")
	max_data_class: DataClass = Field(default="internal", description="Most sensitive data class this model is cleared for; cannot exceed its key's")
	regions: list[Region] = Field(min_length=1, max_length=4, description="Regions where the model processes data")
	risk_rating: Rating = "medium"
	retention_days: int | None = Field(default=None, ge=0, le=3650, description="How long the provider keeps prompts; null if unknown")
	trains_on_data: bool = False
	capabilities: list[Capability] = Field(default_factory=list, max_length=20)
	cost_tier: Rating | None = None
	owner: str | None = Field(default=None, max_length=200)
	enabled: bool = True

	@field_validator("regions", "capabilities")
	@classmethod
	def _no_duplicates(cls, value: list) -> list:
		return _unique(value)


class ModelRegistryUpdate(BaseModel):
	"""Partial update. The model id is fixed: delete and recreate to rename."""

	model_config = ConfigDict(extra="forbid")

	provider_key_id: UUID | None = Field(default=None, description="null detaches the key")
	max_data_class: DataClass | None = None
	regions: list[Region] | None = Field(default=None, min_length=1, max_length=4)
	risk_rating: Rating | None = None
	retention_days: int | None = Field(default=None, ge=0, le=3650)
	trains_on_data: bool | None = None
	capabilities: list[Capability] | None = Field(default=None, max_length=20)
	cost_tier: Rating | None = None
	owner: str | None = Field(default=None, max_length=200)
	enabled: bool | None = None

	@field_validator("max_data_class", "regions", "risk_rating", "trains_on_data", "capabilities", "enabled", mode="before")
	@classmethod
	def _not_null(cls, value):
		if value is None:
			raise ValueError("cannot be null; omit the field to leave it unchanged")
		return value

	@field_validator("regions", "capabilities")
	@classmethod
	def _no_duplicates(cls, value: list | None) -> list | None:
		return None if value is None else _unique(value)


class ModelRegistryResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	model_id: str
	provider: str
	provider_key_id: UUID | None
	max_data_class: str
	regions: list[str]
	risk_rating: str
	retention_days: int | None
	trains_on_data: bool
	capabilities: list[str]
	cost_tier: str | None
	owner: str | None
	enabled: bool
	created_at: datetime
	updated_at: datetime
