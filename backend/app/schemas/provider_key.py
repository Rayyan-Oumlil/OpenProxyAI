"""LLM provider key schemas — CRUD request/response (key values always masked)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.data_class import DataClass

Region = Literal["us", "eu", "ap", "global"]


class ProviderKeyCreateRequest(BaseModel):
	provider: str = Field(min_length=1, max_length=50)
	key_alias: str = Field(min_length=1, max_length=100)
	api_key: str | None = Field(default=None, min_length=8, description="Raw API key: stored encrypted, never returned. Or use vault_path.")
	vault_path: str | None = Field(default=None, max_length=500, description="Read the key from Vault (KV v2) at this path instead; it must be inside your organization's folder.")
	vault_field: str | None = Field(default=None, max_length=100, description="The field in that secret. Default: api_key.")
	weight: int = Field(default=1, ge=1, le=100)
	region: Region = Field(default="us", description="Data region: us, eu, ap, or global")
	api_base: str | None = Field(default=None, max_length=500, description="Custom endpoint (vLLM, Ollama, private gateway). None uses the provider's own.")
	max_data_class: DataClass = Field(default="internal", description="Most sensitive data class this endpoint may receive")
	is_internal: bool = Field(default=False, description="Endpoint is inside your own network")

	@model_validator(mode="after")
	def _exactly_one_secret_source(self) -> "ProviderKeyCreateRequest":
		if (self.api_key is None) == (self.vault_path is None):
			raise ValueError("send exactly one of api_key and vault_path")
		if self.vault_field is not None and self.vault_path is None:
			raise ValueError("vault_field only goes with vault_path")
		return self


class ProviderKeyUpdateRequest(BaseModel):
	"""Partial update — only provided fields are changed."""

	key_alias: str | None = Field(default=None, min_length=1, max_length=100)
	weight: int | None = Field(default=None, ge=1, le=100)
	is_active: bool | None = None
	region: Region | None = None
	api_base: str | None = Field(default=None, max_length=500, description="null clears the custom endpoint")
	max_data_class: DataClass | None = None
	is_internal: bool | None = None

	@field_validator("max_data_class", "is_internal", mode="before")
	@classmethod
	def _not_null(cls, value):
		if value is None:
			raise ValueError("cannot be null; omit the field to leave it unchanged")
		return value


class ProviderKeyResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	provider: str
	key_alias: str
	secret_source: str = "local"  # "vault" when the key is read from Vault
	vault_path: str | None = None
	key_prefix: str  # first 8 chars + "…" — raw key is never returned
	weight: int
	is_active: bool
	region: str
	api_base: str | None = None
	max_data_class: str = "internal"
	is_internal: bool = False
	created_at: datetime
	# Circuit breaker state (when CIRCUIT_BREAKER_ENABLED): Unix timestamp when circuit closes, or None if closed
	circuit_open_until: float | None = None
	# Adaptive LB metrics (when ADAPTIVE_LB_ENABLED): sampled from request_logs
	latency_p99_ms: float | None = None
	error_rate: float | None = None
	effective_weight: int | None = None
	# Provider health-check job (PROVIDER_HEALTH_CHECK_ENABLED): unknown until the first check has run
	health_status: str = "unknown"
	consecutive_failures: int = 0
	last_health_check_at: datetime | None = None
