"""Experiment schemas — CRUD and results for A/B testing."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.request_score import SCORE_NAME_PATTERN


class ExperimentVariantCreate(BaseModel):
	model: str = Field(min_length=1, max_length=100)
	traffic_weight: int = Field(default=50, ge=1, le=100)


class AdaptiveSettings(BaseModel):
	"""How an experiment steers its own traffic. ``static`` keeps the weights an admin set; ``adaptive`` lets a job move them
	toward the better variant as feedback arrives and stop the test, naming a winner, once one is clearly best."""

	mode: Literal["static", "adaptive"] | None = None
	metric: str | None = Field(default=None, pattern=SCORE_NAME_PATTERN)  # a score name whose values are 0 to 1, e.g. thumbs
	min_samples_per_variant: int | None = Field(default=None, ge=20, le=1_000_000)  # nothing is decided below this
	delta: float | None = Field(default=None, ge=0.001, le=0.2)  # stop when one variant is best with chance at least 1 - delta
	weight_floor: int | None = Field(default=None, ge=1, le=20)  # no variant gets less traffic than this percent


class ExperimentCreate(AdaptiveSettings):
	name: str = Field(min_length=1, max_length=255)
	target_model: str = Field(min_length=1, max_length=100)
	variants: list[ExperimentVariantCreate] = Field(min_length=1)


class ExperimentUpdate(AdaptiveSettings):
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
	mode: str = "static"
	metric: str | None = None
	min_samples_per_variant: int = 30
	delta: float = 0.01
	weight_floor: int = 5
	winner_variant_id: uuid.UUID | None = None
	stopped_reason: str | None = None  # winner or manual
	adaptive_error: str | None = None  # why the periodic job could not update this test
	adaptive_updated_at: datetime | None = None


class ScoreAggregate(BaseModel):
	name: str
	avg: float
	count: int


class VariantMetrics(BaseModel):
	variant_id: uuid.UUID | None = None  # null for rows logged before variants were tracked by id
	model: str
	traffic_weight: int | None = None
	request_count: int
	avg_latency_ms: float | None
	total_cost_usd: Decimal
	total_prompt_tokens: int
	total_completion_tokens: int
	policy_violations: int
	scores: list[ScoreAggregate] = Field(default_factory=list)
	probability_best: float | None = None  # adaptive tests only: the chance this variant is the best one


class AdaptiveStatus(BaseModel):
	metric: str
	ready: bool  # every variant has at least min_samples_per_variant scores
	min_samples_per_variant: int
	delta: float
	samples: dict[str, int]  # scores seen per variant id
	winner_variant_id: uuid.UUID | None
	stopped_reason: str | None
	error: str | None


class ExperimentResultsResponse(BaseModel):
	variants: list[VariantMetrics]
	adaptive: AdaptiveStatus | None = None
