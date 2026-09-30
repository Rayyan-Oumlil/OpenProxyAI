"""Pydantic Settings — all configuration loaded from environment variables."""

import re
from typing import Any

from pydantic import field_validator, model_validator
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
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1_440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    AUTH_RATE_LIMIT_MAX_ATTEMPTS: int = 12
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://openproxyai:openproxyai_dev@postgres:5432/openproxyai"
    )
    # Role request-path connections switch to (SET ROLE) so row-level security applies
    # even when DATABASE_URL logs in as a superuser or table owner.
    DB_APP_ROLE: str = "app_user"

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

    # ── Router Strategy ───────────────────────────────────────────────
    # simple_shuffle (default) | round_robin | lowest_latency
    ROUTER_STRATEGY: str = "simple_shuffle"

    # ── Provider Health Check ─────────────────────────────────────────
    PROVIDER_HEALTH_CHECK_ENABLED: bool = False
    PROVIDER_HEALTH_FAILURE_THRESHOLD: int = 3

    # ── Circuit Breaker ────────────────────────────────────────────────
    CIRCUIT_BREAKER_ENABLED: bool = False
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 60

    # ── Key Rotation Scheduler ─────────────────────────────────────────
    KEY_ROTATION_SCHEDULER_ENABLED: bool = False
    KEY_ROTATION_INTERVAL_DAYS: int = 30

    # ── Experiment Eval Hook (LLM-as-judge / external callback) ─────────
    EVAL_HOOK_URL: str = ""  # POST prompt+response, expect {"scores": [...]} or {"score": n}
    EVAL_LLM_MODEL: str = ""  # e.g. openai/gpt-4o for LLM-as-judge; uses litellm env keys

    # ── Adaptive Load Balancing ─────────────────────────────────────────
    ADAPTIVE_LB_ENABLED: bool = False
    ADAPTIVE_LB_SAMPLE_MINUTES: int = 10
    ADAPTIVE_LB_WEIGHT_FLOOR: float = 0.1  # min effective weight multiplier (B2)

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
    PRESIDIO_ENTITIES: list[str] = [
        "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
        "US_SSN", "US_PASSPORT", "PERSON", "IP_ADDRESS",
        "IBAN_CODE", "MEDICAL_LICENSE",
    ]
    PRESIDIO_SCORE_THRESHOLD: float = 0.7

    # ── Cache (exact-match L2) ──────────────────────────────────────
    CACHE_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 3600

    # ── Semantic Cache (L1 + L3 pgvector) ───────────────────────────
    SEMANTIC_CACHE_ENABLED: bool = False
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = 0.95
    SEMANTIC_CACHE_EMBEDDING_MODEL: str = "text-embedding-3-small"
    SEMANTIC_CACHE_MAX_ENTRIES_PER_ORG: int = 10000
    SEMANTIC_CACHE_L1_MAX_SIZE: int = 1000
    SEMANTIC_CACHE_L1_TTL_SECONDS: int = 300
    SEMANTIC_CACHE_COST_PER_TOKEN_ESTIMATE_USD: float = 0.00003

    # ── Cost Anomaly Detection ───────────────────────────────────────
    COST_ANOMALY_MULTIPLIER: float = 3.0
    COST_ANOMALY_MIN_BASELINE_DAYS: int = 3

    # ── Prometheus ───────────────────────────────────────────────────
    PROMETHEUS_ENABLED: bool = True

    # ── Air-gap mode (Data Residency Tier 2) ─────────────────────────
    # When True: no outbound telemetry (Langfuse, ClickHouse, spend reports, Stripe metered sync).
    # LICENSE_KEY required when AIRGAP_MODE=true — startup fails without valid key.
    AIRGAP_MODE: bool = False
    LICENSE_KEY: str = ""

    # ── ClickHouse analytics dual-write ──────────────────────────────
    CLICKHOUSE_URL: str = ""                    # e.g. "clickhouse://localhost:8123"
    CLICKHOUSE_DATABASE: str = "openproxy"

    # ── Langfuse (optional observability) ─────────────────────────────
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # ── Stripe Billing ────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_STARTER_PRICE_ID: str = ""
    STRIPE_GROWTH_PRICE_ID: str = ""
    # Metered usage (Stripe price with usage_type=metered, billing_scheme=per_unit, aggregate_usage=sum)
    STRIPE_METERED_PRICE_ID: str = ""
    # Optional fixed recurring line item paired with metered usage (e.g. platform fee)
    STRIPE_METERED_BASE_PRICE_ID: str = ""
    STRIPE_SUCCESS_URL: str = "http://localhost:5173/billing?success=1"
    STRIPE_CANCEL_URL: str = "http://localhost:5173/billing?canceled=1"

    # Stripe webhook rate limit (requests per minute per IP; Stripe retries, so keep generous)
    STRIPE_WEBHOOK_RATE_LIMIT_RPM: int = 120

    # Metered billing sidecar (hourly Stripe usage record sync)
    METERED_SYNC_ENABLED: bool = True
    METERED_INCLUDED_TOKENS_MONTHLY: int = 1_000_000

    # ── Batched spend writes (Redis queue → Postgres) ─────────────────
    BATCH_SPEND_ENABLED: bool = False
    BATCH_SPEND_FLUSH_INTERVAL_SECONDS: int = 60
    BATCH_SPEND_MAX_SIZE: int = 500

    # ── Spend reports (Slack / email digest) ───────────────────────────
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@openproxyai.com"

    # ── Security ──────────────────────────────────────────────────────
    # When True, trust X-Forwarded-For for client IP (use only behind a trusted proxy).
    # See docs/compliance/self-hosted-security.md and deployment guides.
    TRUSTED_PROXY: bool = False

    # SSO exchange-code rate limit (requests per minute per IP; prevents brute-force)
    SSO_EXCHANGE_RATE_LIMIT_RPM: int = 30

    # ── SSO ──────────────────────────────────────────────────────────
    # Public base URL of the API (e.g. https://api.example.com). Used to validate
    # redirect_uri in OIDC flows — only {APP_BASE_URL}/api/v1/auth/sso/callback is allowed.
    APP_BASE_URL: str = "http://localhost:8000"
    # Frontend base URL for SSO redirect after auth (e.g. https://app.example.com).
    # Used when redirecting with one-time code; defaults to CORS_ORIGINS first origin.
    FRONTEND_BASE_URL: str = ""

    # ── CORS ─────────────────────────────────────────────────────────
    # Stored as str so pydantic-settings v2 doesn't try to JSON-decode it
    # before validators run. Parsing happens in middleware/cors.py.
    CORS_ORIGINS: str = (
        "http://127.0.0.1:5175,http://localhost:5175,"
        "http://127.0.0.1:5174,http://localhost:5174,"
        "http://127.0.0.1:5173,http://localhost:5173,"
        "http://127.0.0.1:3000,http://localhost:3000"
    )

    @field_validator("DB_APP_ROLE")
    @classmethod
    def validate_db_app_role(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", v):
            raise ValueError(
                f"DB_APP_ROLE must be a plain Postgres identifier, got {v!r}. "
                "It is used in SET ROLE; leaving it empty would disable row-level security."
            )
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

    @model_validator(mode="after")
    def validate_production_secret_key(self) -> "Settings":
        """Reject the insecure default SECRET_KEY when running in production."""
        if self.APP_ENV == "production" and self.SECRET_KEY == "dev-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY must be changed in production. "
                "Set a cryptographically random 32+ character string in the SECRET_KEY environment variable."
            )
        return self

    @model_validator(mode="after")
    def validate_airgap_license(self) -> "Settings":
        """When AIRGAP_MODE=true, LICENSE_KEY must be set and valid (min 16 chars)."""
        if self.AIRGAP_MODE:
            key = (self.LICENSE_KEY or "").strip()
            if not key or len(key) < 16:
                raise ValueError(
                    "AIRGAP_MODE=true requires a valid LICENSE_KEY (min 16 characters). "
                    "Set LICENSE_KEY environment variable."
                )
        return self

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
    "free":       {"max_users": 3,   "max_api_keys": 5,   "sso_enabled": False, "pii_detection": False, "audit_retention_days": 7,   "included_tokens_monthly": -1},
    "starter":    {"max_users": 50,  "max_api_keys": 50,  "sso_enabled": False, "pii_detection": True,  "audit_retention_days": 30,  "included_tokens_monthly": -1},
    "growth":     {"max_users": 200, "max_api_keys": 200, "sso_enabled": False, "pii_detection": True,  "audit_retention_days": 90,  "included_tokens_monthly": -1},
    "enterprise": {"max_users": -1,  "max_api_keys": -1,  "sso_enabled": True,  "pii_detection": True,  "audit_retention_days": 365, "included_tokens_monthly": -1},
    "metered":    {"max_users": 500, "max_api_keys": 500, "sso_enabled": False, "pii_detection": True,  "audit_retention_days": 90,  "included_tokens_monthly": -1},
}
