"""Pydantic Settings — all configuration loaded from environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────
    APP_NAME: str = "OpenProxyAI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1_440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    AUTH_RATE_LIMIT_MAX_ATTEMPTS: int = 12
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://openproxyai:openproxyai_dev@postgres:5432/openproxyai"
    )

    # ── Redis ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"

    # ── LLM Provider Keys ────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    AZURE_API_KEY: str = ""
    AZURE_API_BASE: str = ""

    # ── Rate Limits ──────────────────────────────────────────────────
    DEFAULT_RATE_LIMIT_RPM: int = 60
    DEFAULT_RATE_LIMIT_TPM: int = 100_000
    DEFAULT_BUDGET_DAILY_USD: float = 50.0

    # ── Policy Engine ────────────────────────────────────────────────
    POLICY_ENFORCEMENT_MODE: str = "off"
    POLICY_ALLOWED_MODELS: list[str] = []
    POLICY_BLOCKED_KEYWORDS: list[str] = []
    POLICY_PII_DETECTION_ENABLED: bool = True

    # ── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://127.0.0.1:5175",
        "http://localhost:5175",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("POLICY_ALLOWED_MODELS", "POLICY_BLOCKED_KEYWORDS", mode="before")
    @classmethod
    def parse_policy_lists(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except (json.JSONDecodeError, TypeError):
                pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return [str(item).strip() for item in v if str(item).strip()]


settings = Settings()
