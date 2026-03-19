"""OpenAI-compatible model list response schemas."""

from pydantic import BaseModel, ConfigDict


class ModelResponse(BaseModel):
	"""Single model entry in the /v1/models list."""

	id: str
	object: str = "model"
	owned_by: str

	model_config = ConfigDict(extra="forbid")


class ModelListResponse(BaseModel):
	"""OpenAI-compatible /v1/models response."""

	object: str = "list"
	data: list[ModelResponse]

	model_config = ConfigDict(extra="forbid")
