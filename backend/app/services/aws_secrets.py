"""Reading provider keys from AWS Secrets Manager instead of storing them (a sibling of ``vault_client``).

The same rules as Vault, for the same reasons:

- **Tenant isolation of names.** The gateway has one AWS identity; an org admin names a secret. Without a rule that admin could name
  another tenant's. The name must sit under the org's own prefix (``AWS_SECRET_PREFIX``, default ``openproxyai/{org_id}/``), checked at
  creation and on every read. Only *names* are accepted, never ARNs: an ARN can point at another account or region.
- **Operator-held credentials.** They come from the gateway's environment or its IAM role (boto3's normal chain), never from org data.
- **Fails hard.** An unreadable secret is an error for that key, never a fall back to another source. The value is never logged and an
  error carries the AWS error *code* only.
- **Short cache** (``AWS_SECRET_CACHE_SECONDS``) so a request does not wait on AWS and a rotated secret is picked up promptly.

The secret may be a plain string, or JSON with a field to read (``aws_secret_field``, default ``api_key``).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.services.external_secret_error import ExternalSecretError
from app.utils.logging import get_logger

logger = get_logger(__name__)

NAME_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./+=@-]{0,510}[A-Za-z0-9_]|[A-Za-z0-9_]")
FIELD_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,100}")
DEFAULT_FIELD = "api_key"


class AwsSecretError(ExternalSecretError):
    """AWS could not give the secret. ``str(error)`` is safe to log and to show an admin: no secret value, no response body."""


def configured() -> bool:
    return bool(settings.AWS_SECRETS_ENABLED)


def required_prefix(org_id: uuid.UUID) -> str:
    return settings.AWS_SECRET_PREFIX.replace("{org_id}", str(org_id))


def validate_name(org_id: uuid.UUID, name: str, field: str | None = None) -> None:
    """Raises ValueError unless ``name`` is a plain secret name inside this org's prefix (and ``field`` a plain field name)."""
    if not NAME_PATTERN.fullmatch(name or "") or ".." in name or "//" in name or name.lower().startswith("arn:"):
        raise ValueError("the secret name may only contain letters, digits and _ . / + = @ -, without '..', and must be a name, not an ARN")
    prefix = required_prefix(org_id)
    if not name.startswith(prefix) or name == prefix:
        raise ValueError(f"the secret name must be inside this organization's folder: {prefix}")
    if field is not None and not FIELD_PATTERN.fullmatch(field):
        raise ValueError("the field may only contain letters, digits, '_', '-' and '.'")


@dataclass
class _Cached:
    value: str
    expires: float


def _default_client() -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "secretsmanager", region_name=settings.AWS_SECRETS_REGION or None,
        config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 2}),
    )


class AwsSecretsClient:
    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self._factory = client_factory or _default_client
        self._client: Any = None
        self._secrets: dict[tuple[str, str], _Cached] = {}

    def _get(self, name: str) -> str:
        if self._client is None:
            self._client = self._factory()
        try:
            response = self._client.get_secret_value(SecretId=name)
        except Exception as exc:  # noqa: BLE001  (boto raises ClientError, BotoCoreError, ...; only the code is safe to repeat)
            code = getattr(exc, "response", {}).get("Error", {}).get("Code") if hasattr(exc, "response") else None
            raise AwsSecretError(f"AWS could not give the secret ({code or type(exc).__name__})") from None
        value = response.get("SecretString")
        if not isinstance(value, str) or not value:
            raise AwsSecretError("the secret has no text value (binary secrets are not supported)")
        return value

    async def read(self, org_id: uuid.UUID, name: str, field: str | None = None) -> str:
        field = field or DEFAULT_FIELD
        try:
            validate_name(org_id, name, field)
        except ValueError as exc:
            raise AwsSecretError(str(exc)) from None
        if not configured():
            raise AwsSecretError("AWS Secrets Manager is not enabled on this gateway")
        cache_key = (name, field)
        cached = self._secrets.get(cache_key)
        if cached and time.monotonic() < cached.expires:
            return cached.value
        raw = await asyncio.to_thread(self._get, name)
        value = raw
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            value = parsed.get(field)
            if not isinstance(value, str) or not value:
                raise AwsSecretError(f"the secret has no '{field}' field")
        elif field != DEFAULT_FIELD:
            raise AwsSecretError(f"the secret is not JSON, so it has no '{field}' field")
        self._secrets[cache_key] = _Cached(value, time.monotonic() + settings.AWS_SECRET_CACHE_SECONDS)
        return value

    def forget(self) -> None:
        self._secrets.clear()
        self._client = None


aws_secrets = AwsSecretsClient()
