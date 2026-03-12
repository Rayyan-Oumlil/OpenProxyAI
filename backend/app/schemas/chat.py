"""Chat completion schemas — OpenAI-compatible request/response format."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
	role: Literal["system", "user", "assistant", "tool"]
	content: str | list[Any]


class ChatCompletionRequest(BaseModel):
	model: str
	messages: list[Message] = Field(min_length=1)
	temperature: float | None = None
	max_tokens: int | None = None
	stream: bool = False
	top_p: float | None = None
	frequency_penalty: float | None = None
	presence_penalty: float | None = None
	stop: str | list[str] | None = None
	user: str | None = None

	model_config = ConfigDict(extra="allow")


class EmbeddingRequest(BaseModel):
	model: str
	input: str | list[str]
	encoding_format: str = "float"

