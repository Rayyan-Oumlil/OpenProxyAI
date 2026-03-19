"""Playground schemas — prompt templates and model comparison."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class VariableSchemaItem(BaseModel):
    name: str
    type: str = "string"
    default: str | None = None
    required: bool = False


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    system_message: str | None = None
    user_template: str = Field(..., min_length=1)
    variables_schema: list[VariableSchemaItem] = Field(default_factory=list)


class PromptTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    system_message: str | None = None
    user_template: str | None = Field(None, min_length=1)


class PromptTemplateResponse(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None
    system_message: str | None
    user_template: str
    variables_schema: list[dict[str, Any]]
    version: int
    is_active: bool
    created_by: str | None
    created_at: str
    updated_at: str


class Message(BaseModel):
    role: str
    content: str


class PlaygroundCompareRequest(BaseModel):
    models: list[str] = Field(..., min_length=2, max_length=4)
    messages: list[Message] = Field(..., min_length=1)
    temperature: float | None = None
    max_tokens: int | None = None


class PlaygroundCompareResult(BaseModel):
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal
    latency_ms: int
    ttft_ms: int | None = None
    error: str | None = None


class PlaygroundCompareResponse(BaseModel):
    results: list[PlaygroundCompareResult]
