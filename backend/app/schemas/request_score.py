"""Request score schemas — quality score submission and response."""

from pydantic import BaseModel, Field


class ScoreItem(BaseModel):
	name: str = Field(min_length=1, max_length=100)
	value: float = Field(ge=-1e6, le=1e6)


class RequestScoresSubmit(BaseModel):
	scores: list[ScoreItem] = Field(min_length=1, max_length=20)


class RequestScoresSubmitResponse(BaseModel):
	submitted: int
