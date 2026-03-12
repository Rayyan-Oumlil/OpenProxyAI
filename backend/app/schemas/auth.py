"""Auth schemas — login, register, token response, API key create/response."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8)
	name: str = Field(min_length=1, max_length=255)
	org_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
	email: EmailStr
	password: str


class TokenResponse(BaseModel):
	access_token: str
	refresh_token: str
	token_type: str = "bearer"
	expires_in: int


class APIKeyCreateRequest(BaseModel):
	name: str = Field(min_length=1, max_length=100)
	permissions: list[str] = Field(default_factory=lambda: ["proxy:llm"])
	expires_at: datetime | None = None

	@field_validator("permissions")
	@classmethod
	def validate_permissions(cls, value: list[str]) -> list[str]:
		return value or ["proxy:llm"]


class APIKeyResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	name: str | None
	key_prefix: str
	permissions: list[str]
	is_active: bool
	expires_at: datetime | None
	created_at: datetime


class APIKeyCreatedResponse(APIKeyResponse):
	key: str
	warning: str = "Store this key securely. It will not be shown again."


class UserMeResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	org_id: uuid.UUID
	email: EmailStr
	name: str | None
	role: str
	is_active: bool

