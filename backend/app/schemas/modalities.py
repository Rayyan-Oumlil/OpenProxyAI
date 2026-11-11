"""Request schemas for the non-chat endpoints (Phase 5). Limits are here because everything in a request is scanned by policy."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_MODEL_CHARS = 100
Model = Annotated[str, StringConstraints(min_length=1, max_length=MAX_MODEL_CHARS)]

MAX_RERANK_DOCUMENTS = 1_000
MAX_RERANK_QUERY_CHARS = 10_000
MAX_RERANK_DOCUMENT_CHARS = 50_000
MAX_RERANK_TOTAL_CHARS = 1_000_000


class RerankRequest(BaseModel):
	"""Cohere-style rerank: ``documents`` are strings (or ``{"text": ...}`` objects), returned ordered by relevance to ``query``."""

	model_config = ConfigDict(extra="forbid")

	model: Model
	query: str = Field(min_length=1, max_length=MAX_RERANK_QUERY_CHARS)
	documents: list[str | dict[str, str]] = Field(min_length=1, max_length=MAX_RERANK_DOCUMENTS)
	top_n: int | None = Field(default=None, ge=1, le=MAX_RERANK_DOCUMENTS)
	return_documents: bool = True

	@field_validator("documents")
	@classmethod
	def _sized(cls, documents: list[str | dict[str, str]]) -> list[str | dict[str, str]]:
		total = 0
		for document in documents:
			text = document if isinstance(document, str) else document.get("text")
			if not isinstance(text, str):
				raise ValueError('a document is a string or {"text": "..."}')
			if len(text) > MAX_RERANK_DOCUMENT_CHARS:
				raise ValueError(f"a document is longer than {MAX_RERANK_DOCUMENT_CHARS} characters")
			total += len(text)
		if total > MAX_RERANK_TOTAL_CHARS:
			raise ValueError(f"the documents together are longer than {MAX_RERANK_TOTAL_CHARS} characters")
		return documents

	def texts(self) -> list[str]:
		return [d if isinstance(d, str) else d["text"] for d in self.documents]


MAX_IMAGE_PROMPT_CHARS = 4_000
MAX_IMAGES_PER_REQUEST = 4
ImageSize = Literal["auto", "256x256", "512x512", "1024x1024", "1024x1536", "1536x1024", "1024x1792", "1792x1024"]


class ImageRequest(BaseModel):
	"""OpenAI-style image generation. The prompt is the only text, and it is scanned like any prompt."""

	model_config = ConfigDict(extra="forbid")

	model: Model
	prompt: str = Field(min_length=1, max_length=MAX_IMAGE_PROMPT_CHARS)
	n: int = Field(default=1, ge=1, le=MAX_IMAGES_PER_REQUEST)
	size: ImageSize | None = None
	quality: Literal["standard", "hd", "low", "medium", "high", "auto"] | None = None
	style: Literal["vivid", "natural"] | None = None
	response_format: Literal["url", "b64_json"] | None = None
	user: str | None = Field(default=None, max_length=200)


MAX_SPEECH_INPUT_CHARS = 4_096
SPEECH_FORMATS = {"mp3": "audio/mpeg", "opus": "audio/opus", "aac": "audio/aac", "flac": "audio/flac", "wav": "audio/wav", "pcm": "audio/pcm"}


class SpeechRequest(BaseModel):
	"""Text to speech. The text is scanned like any prompt; the audio that comes back is derived from it."""

	model_config = ConfigDict(extra="forbid")

	model: Model
	input: str = Field(min_length=1, max_length=MAX_SPEECH_INPUT_CHARS)
	voice: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
	response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
	speed: float | None = Field(default=None, ge=0.25, le=4.0)


MAX_AUDIO_BYTES = 25 * 1024 * 1024  # the limit OpenAI applies; reading stops one byte past it
AUDIO_EXTENSIONS = frozenset({"flac", "m4a", "mp3", "mp4", "mpeg", "mpga", "oga", "ogg", "wav", "webm"})
TRANSCRIPT_FORMATS = ("json", "text", "srt", "verbose_json", "vtt")


class TranscriptionRequest(BaseModel):
	"""Speech to text. ``data`` is the audio, already size-checked by the route. Its content cannot be read, so the gateway treats the
	request as uninspected for classification; only ``prompt`` (an optional text hint to the model) is scanned."""

	model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

	model: Model
	filename: str = Field(min_length=1, max_length=255)
	data: bytes = Field(repr=False)
	language: str | None = Field(default=None, pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
	prompt: str | None = Field(default=None, max_length=1_000)
	response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = "json"
	temperature: float | None = Field(default=None, ge=0, le=1)

	@field_validator("filename")
	@classmethod
	def _audio_extension(cls, name: str) -> str:
		extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
		if extension not in AUDIO_EXTENSIONS:
			raise ValueError("the file must be audio: " + ", ".join(sorted(AUDIO_EXTENSIONS)))
		return name

	@field_validator("data")
	@classmethod
	def _not_empty(cls, data: bytes) -> bytes:
		if not data:
			raise ValueError("the audio file is empty")
		if len(data) > MAX_AUDIO_BYTES:
			raise ValueError(f"the audio file is larger than {MAX_AUDIO_BYTES} bytes")
		return data


# -- responses ---------------------------------------------------------------------------------------

MAX_RESPONSES_INPUT_ITEMS = 500
INPUT_ITEM_TYPES_WITH_NO_TEXT = frozenset({"input_image", "input_file", "input_audio"})


class ResponsesRequest(BaseModel):
    """OpenAI Responses API, narrowed to what the gateway can govern.

    Unknown fields are refused rather than forwarded: this API grows quickly, and a field that makes the provider keep state, run a
    tool or fetch a URL would otherwise pass straight through. ``store`` and ``previous_response_id`` need the org to allow provider
    state; only client-side ``function`` tools are accepted; streaming is not supported yet.
    """

    model_config = ConfigDict(extra="forbid")

    model: Model
    input: str | list[dict[str, Any]] = Field(max_length=None)
    instructions: str | None = Field(default=None, max_length=50_000)
    max_output_tokens: int | None = Field(default=None, ge=1, le=200_000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    tools: list[dict[str, Any]] | None = Field(default=None, max_length=128)
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
    text: dict[str, Any] | None = None  # output format (e.g. a JSON schema)
    metadata: dict[str, str] | None = Field(default=None, max_length=16)
    user: str | None = Field(default=None, max_length=200)
    truncation: Literal["auto", "disabled"] | None = None
    store: bool | None = None
    previous_response_id: str | None = Field(default=None, max_length=200)
    stream: Literal[False] | None = None  # streaming is refused with a clear 422, not silently ignored

    @field_validator("input")
    @classmethod
    def _bounded(cls, value: Any) -> Any:
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("input cannot be blank")
            if len(value) > 500_000:
                raise ValueError("input is longer than 500000 characters")
        elif not value or len(value) > MAX_RESPONSES_INPUT_ITEMS:
            raise ValueError(f"input must have between 1 and {MAX_RESPONSES_INPUT_ITEMS} items")
        return value

    @field_validator("tools")
    @classmethod
    def _client_side_tools_only(cls, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        for tool in tools or []:
            if tool.get("type") != "function":
                raise ValueError(
                    f"tool type {tool.get('type')!r} runs at the provider and is not allowed; only client-side \"function\" tools are"
                )
        return tools

    def has_uninspectable_input(self) -> bool:
        """An image, file or audio part: content the gateway cannot read."""
        if isinstance(self.input, str):
            return False
        for item in self.input:
            content = item.get("content")
            parts = content if isinstance(content, list) else []
            if item.get("type") in INPUT_ITEM_TYPES_WITH_NO_TEXT or any(isinstance(p, dict) and p.get("type") in INPUT_ITEM_TYPES_WITH_NO_TEXT for p in parts):
                return True
        return False
