"""Experiment schemas — CRUD and results for A/B testing."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExperimentVariantCreate(BaseModel):
	model: str = Field(min_length=1, max_length=100)
	traffic_weight: int = Field(default=50, ge=1, le=100)


class ExperimentCreate(BaseModel):
	name: str = Field(min_length=1, max_length=255)
	target_model: str = Field(min_length=1, max_length=100)
	variants: list[ExperimentVariantCreate] = Field(min_length=1)


class ExperimentUpdate(BaseModel):
	name: str | None = Field(default=None, min_length=1, max_length=255)
	is_active: bool | None = None
	variants: list[ExperimentVariantCreate] | None = Field(default=None, min_length=1)


class ExperimentVariantResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	experiment_id: uuid.UUID
	model: str
	traffic_weight: int


class ExperimentResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	org_id: uuid.UUID
	name: str
	target_model: str
	is_active: bool
	variants: list[ExperimentVariantResponse]
	created_at: datetime


class ScoreAggregate(BaseModel):
	name: str
	avg: float
	count: int


class VariantMetrics(BaseModel):
	model: str
	request_count: int
	avg_latency_ms: float | None
	total_cost_usd: Decimal
	total_prompt_tokens: int
	total_completion_tokens: int
	policy_violations: int
	scores: list[ScoreAggregate] = Field(default_factory=list)


class ExperimentResultsResponse(BaseModel):
	variants: list[VariantMetrics]
