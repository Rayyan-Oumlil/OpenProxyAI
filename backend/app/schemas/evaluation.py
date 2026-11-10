"""Evaluator and eval-run schemas (Phase 3, slice 4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MAX_RUN_ITEMS = 500
DEFAULT_RUN_ITEMS = 100
MAX_RUN_COST_USD = 50.0
DEFAULT_RUN_COST_USD = 1.0
MAX_ACTIVE_RUNS = 2

Name = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
ModelName = Annotated[str, StringConstraints(pattern=r"^[^/\s]+/\S+$", max_length=100)]  # provider/model


class EvaluatorCreate(BaseModel):
	model_config = ConfigDict(extra="forbid")

	name: Name
	type: Literal["exact", "regex", "llm_judge"]
	config: dict = Field(default_factory=dict)


class EvaluatorResponse(BaseModel):
	id: uuid.UUID
	name: str
	type: str
	config: dict
	created_at: datetime


class EvalRunCreate(BaseModel):
	model_config = ConfigDict(extra="forbid")

	dataset_id: uuid.UUID
	evaluator_id: uuid.UUID
	candidate_model: ModelName
	system_prompt: str | None = Field(default=None, max_length=8000)
	prompt_template_id: uuid.UUID | None = None  # the system prompt defaults to this template's
	max_items: int = Field(default=DEFAULT_RUN_ITEMS, ge=1, le=MAX_RUN_ITEMS)
	max_cost_usd: float = Field(default=DEFAULT_RUN_COST_USD, ge=0.01, le=MAX_RUN_COST_USD)


class EvalRunResponse(BaseModel):
	id: uuid.UUID
	dataset_id: uuid.UUID | None
	evaluator_id: uuid.UUID | None
	evaluator: dict  # name, type and config as they were when the run started
	prompt_template_id: uuid.UUID | None
	candidate_model: str
	status: str
	total_items: int
	completed_items: int
	scored_items: int  # completed without an error; the average and pass rate are over these
	failed_items: int  # refused, failed or could not be scored: recorded with their reason, left out of the average
	passed_items: int
	mean_score: float | None
	pass_rate: float | None
	cost_usd: float
	max_cost_usd: float
	error: str | None
	created_at: datetime
	started_at: datetime | None
	finished_at: datetime | None


class EvalRunItemResponse(BaseModel):
	id: uuid.UUID
	dataset_item_id: uuid.UUID | None
	output: str | None
	score: float | None
	passed: bool | None
	reason: str | None
	error: str | None
	cost_usd: float
	latency_ms: int | None
