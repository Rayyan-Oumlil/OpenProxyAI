"""Pydantic Settings — all configuration loaded from environment variables."""

from typing import Any

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

    # ── Provider Fallback ─────────────────────────────────────────────
    MAX_PROVIDER_FALLBACK_ATTEMPTS: int = 3

    # ── Prompt Injection ML Detection ─────────────────────────────────
    PROMPT_INJECTION_SCORE_THRESHOLD: float = 0.85
    PROMPT_INJECTION_TIMEOUT_SECONDS: float = 2.0
    PROMPT_INJECTION_MIN_TEXT_LENGTH: int = 30

    # ── Policy Engine ────────────────────────────────────────────────
    POLICY_ENFORCEMENT_MODE: str = "off"
    POLICY_ALLOWED_MODELS: list[str] = []
    POLICY_BLOCKED_KEYWORDS: list[str] = []
    POLICY_PII_DETECTION_ENABLED: bool = True

    # ── Presidio NLP PII detection ───────────────────────────────────────
    PRESIDIO_ENTITIES: list = [
        "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
        "US_SSN", "US_PASSPORT", "PERSON", "IP_ADDRESS",
        "IBAN_CODE", "MEDICAL_LICENSE",
    ]
    PRESIDIO_SCORE_THRESHOLD: float = 0.7

    # ── Semantic Cache ───────────────────────────────────────────────
    CACHE_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 3600

    # ── Cost Anomaly Detection ───────────────────────────────────────
    COST_ANOMALY_MULTIPLIER: float = 3.0
    COST_ANOMALY_MIN_BASELINE_DAYS: int = 3

    # ── Prometheus ───────────────────────────────────────────────────
    PROMETHEUS_ENABLED: bool = True

    # ── ClickHouse analytics dual-write ──────────────────────────────
    CLICKHOUSE_URL: str = ""                    # e.g. "clickhouse://localhost:8123"
    CLICKHOUSE_DATABASE: str = "openproxy"

    # ── Langfuse (optional observability) ─────────────────────────────
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

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

    @field_validator("PROMPT_INJECTION_SCORE_THRESHOLD", mode="before")
    @classmethod
    def validate_injection_threshold(cls, v: float | str) -> float:
        value = float(v)
        if not (0.0 < value <= 1.0):
            raise ValueError(
                f"PROMPT_INJECTION_SCORE_THRESHOLD must be in (0, 1], got {value}. "
                "Setting to 0.0 would block all requests; use 1.0 to disable."
            )
        return value

    @field_validator("PROMPT_INJECTION_TIMEOUT_SECONDS", mode="before")
    @classmethod
    def validate_injection_timeout(cls, v: float | str) -> float:
        value = float(v)
        if value <= 0:
            raise ValueError(
                f"PROMPT_INJECTION_TIMEOUT_SECONDS must be positive, got {value}."
            )
        return value

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

# ── Plan Feature Gates (module-level, NOT a pydantic field) ─────────────
PLAN_FEATURES: dict[str, dict[str, Any]] = {
    "free":       {"max_users": 3,   "max_api_keys": 5,   "sso_enabled": False, "pii_detection": False, "audit_retention_days": 7},
    "starter":    {"max_users": 50,  "max_api_keys": 50,  "sso_enabled": False, "pii_detection": True,  "audit_retention_days": 30},
    "growth":     {"max_users": 200, "max_api_keys": 200, "sso_enabled": False, "pii_detection": True,  "audit_retention_days": 90},
    "enterprise": {"max_users": -1,  "max_api_keys": -1,  "sso_enabled": True,  "pii_detection": True,  "audit_retention_days": 365},
}
