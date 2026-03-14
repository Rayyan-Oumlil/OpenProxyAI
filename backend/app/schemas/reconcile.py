"""Schemas for provider usage reconciliation — compare gateway aggregates against provider exports."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderRecord(BaseModel):
	"""Single row from a provider usage export (one model per day)."""

	date: str = Field(..., description="ISO date string YYYY-MM-DD")
	model: str
	requests: int = 0
	input_tokens: int = 0
	output_tokens: int = 0
	cost_usd: float = 0.0


class ReconcileRequest(BaseModel):
	"""Body for POST /reconcile — provider name + list of daily model records."""

	provider: str
	records: list[ProviderRecord]


class ReconcileRowDelta(BaseModel):
	"""Delta for one (date, model) combination: gateway value minus provider value."""

	date: str
	model: str
	# Requests
	gateway_requests: int
	provider_requests: int
	delta_requests: int
	pct_delta_requests: float | None
	# Input tokens
	gateway_input_tokens: int
	provider_input_tokens: int
	delta_input_tokens: int
	pct_delta_input_tokens: float | None
	# Output tokens
	gateway_output_tokens: int
	provider_output_tokens: int
	delta_output_tokens: int
	pct_delta_output_tokens: float | None
	# Cost
	gateway_cost_usd: float
	provider_cost_usd: float
	delta_cost_usd: float
	pct_delta_cost_usd: float | None


class ReconcileSummary(BaseModel):
	"""Totals across all rows in the report."""

	total_gateway_requests: int
	total_provider_requests: int
	total_delta_requests: int
	total_gateway_input_tokens: int
	total_provider_input_tokens: int
	total_delta_input_tokens: int
	total_gateway_output_tokens: int
	total_provider_output_tokens: int
	total_delta_output_tokens: int
	total_gateway_cost_usd: float
	total_provider_cost_usd: float
	total_delta_cost_usd: float


class ReconcileReport(BaseModel):
	"""Full reconciliation report for a provider over a date range."""

	provider: str
	period_start: str
	period_end: str
	total_rows: int
	mismatch_rows: int
	rows: list[ReconcileRowDelta]
	summary: ReconcileSummary
	generated_at: datetime
