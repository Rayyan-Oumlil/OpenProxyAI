"""Request score schemas — quality score submission and response."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# request_scores.value is Numeric(10, 4): anything at or beyond 1e6 overflows the column.
MAX_SCORE_ABS = 999_999.0
SCORE_NAME_PATTERN = r"^[A-Za-z0-9_.:-]{1,100}$"
THUMBS_SCORE_NAME = "thumbs"
THUMBS_VALUES = {"up": 1.0, "down": 0.0}


class ScoreItem(BaseModel):
	name: str = Field(min_length=1, max_length=100)
	value: float = Field(ge=-1e6, le=1e6)


class RequestScoresSubmit(BaseModel):
	scores: list[ScoreItem] = Field(min_length=1, max_length=20)


class RequestScoresSubmitResponse(BaseModel):
	submitted: int


class FeedbackRequest(BaseModel):
	"""One rating of one answer, sent by an application with its API key (``POST /v1/feedback``)."""

	model_config = ConfigDict(extra="forbid")  # a misspelled field fails loudly instead of being ignored

	request_id: UUID  # the x-openproxyai-request-id response header of the request being rated
	score_name: str | None = Field(default=None, pattern=SCORE_NAME_PATTERN)
	value: float | None = Field(default=None, gt=-MAX_SCORE_ABS - 1, lt=MAX_SCORE_ABS + 1)
	thumbs: Literal["up", "down"] | None = None
	comment: str | None = Field(default=None, max_length=2000)

	@model_validator(mode="after")
	def one_rating_with_a_name(self) -> "FeedbackRequest":
		if (self.value is None) == (self.thumbs is None):
			raise ValueError("send exactly one of value or thumbs")
		if self.value is not None and self.score_name is None:
			raise ValueError("score_name is required with a numeric value")
		return self

	@property
	def resolved_name(self) -> str:
		return self.score_name or THUMBS_SCORE_NAME

	@property
	def resolved_value(self) -> float:
		return THUMBS_VALUES[self.thumbs] if self.thumbs is not None else float(self.value)  # type: ignore[arg-type]


class FeedbackResponse(BaseModel):
	request_id: UUID
	score_name: str
	value: float
