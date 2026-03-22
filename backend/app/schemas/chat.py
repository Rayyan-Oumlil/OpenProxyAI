"""Chat completion schemas — OpenAI-compatible request/response format."""

import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Message(BaseModel):
	role: Literal["system", "user", "assistant", "tool"]
	content: str | list[Any]


def _substitute_variables(template: str, variables: dict[str, str]) -> str:
	"""Replace {{name}} placeholders with variables[name]. Missing keys become empty string."""
	def _repl(match: re.Match[str]) -> str:
		return str(variables.get(match.group(1), ""))
	return re.sub(r"\{\{(\w+)\}\}", _repl, template)


class ChatCompletionRequest(BaseModel):
	model: str
	messages: list[Message] = Field(default_factory=list)
	# When prompt_id is set, messages must be empty; template is resolved server-side
	prompt_id: UUID | None = None
	variables: dict[str, str] | None = None
	temperature: float | None = None
	max_tokens: int | None = None
	stream: bool = False
	top_p: float | None = None
	frequency_penalty: float | None = None
	presence_penalty: float | None = None
	stop: str | list[str] | None = None
	user: str | None = None

	model_config = ConfigDict(extra="allow")

	@model_validator(mode="after")
	def messages_or_prompt_id(self):
		has_messages = len(self.messages or []) >= 1
		has_prompt_id = self.prompt_id is not None
		if has_messages and has_prompt_id:
			raise ValueError("prompt_id and messages are mutually exclusive")
		if not has_messages and not has_prompt_id:
			raise ValueError("Provide either messages or prompt_id")
		return self


class EmbeddingRequest(BaseModel):
	model: str
	input: str | list[str]
	encoding_format: str = "float"

