"""Reading provider keys from HashiCorp Vault (KV v2) instead of storing them (Phase 5, slice 5.10).

What makes this safe to offer to org admins:

- **Tenant isolation of paths.** The gateway has one Vault credential; an org admin names a path. Without a rule, that admin could name
  another tenant's secret. Every path must sit under the org's own prefix (``VAULT_PATH_PREFIX``, default ``openproxyai/{org_id}/``),
  and traversal (``..``, a leading slash, odd characters) is refused. The check runs when a key is created and again on every read.
- **Operator-held credentials.** The token, or the AppRole id and secret, come from the gateway's environment, never from org data.
- **TLS required.** A plain ``http://`` address is refused unless the operator sets ``VAULT_ALLOW_INSECURE_HTTP`` (development).
- **Fails hard.** A secret that cannot be read is an error for that key, never a fall back to another source. The value is never
  logged, and error messages carry the status code only, not Vault's response body.
- **Short cache.** A secret is cached in memory for ``VAULT_CACHE_SECONDS`` so a request does not wait on Vault, and a rotated
  secret is picked up within that time.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.external_secret_error import ExternalSecretError
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Matched with fullmatch: with ``$``, Python also accepts a trailing newline.
PATH_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,498}[A-Za-z0-9_]|[A-Za-z0-9_]")
FIELD_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,100}")
DEFAULT_FIELD = "api_key"
REQUEST_TIMEOUT_SECONDS = 3.0
TOKEN_REFRESH_MARGIN_SECONDS = 30


class VaultError(ExternalSecretError):
    """Vault could not give the secret. ``str(error)`` is safe to log and to show an admin: it never holds the secret or Vault's body."""


class VaultNotConfigured(VaultError):
    pass


def configured() -> bool:
    return bool(settings.VAULT_ADDR) and bool(settings.VAULT_TOKEN or (settings.VAULT_ROLE_ID and settings.VAULT_SECRET_ID))


def required_prefix(org_id: uuid.UUID) -> str:
    return settings.VAULT_PATH_PREFIX.replace("{org_id}", str(org_id))


def validate_path(org_id: uuid.UUID, path: str, field: str | None = None) -> None:
    """Raises ValueError when ``path`` is not a plain path inside this org's prefix, or ``field`` is not a plain field name."""
    if not PATH_PATTERN.fullmatch(path or "") or ".." in path or "//" in path:
        raise ValueError("the Vault path may only contain letters, digits, '_', '-', '.' and '/', without '..'")
    prefix = required_prefix(org_id)
    if not path.startswith(prefix) or path == prefix:
        raise ValueError(f"the Vault path must be inside this organization's folder: {prefix}")
    if field is not None and not FIELD_PATTERN.fullmatch(field):
        raise ValueError("the Vault field may only contain letters, digits, '_', '-' and '.'")


@dataclass
class _Cached:
    value: str
    expires: float


class VaultClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport
        self._secrets: dict[tuple[str, str], _Cached] = {}
        self._token: str | None = None
        self._token_expires = 0.0

    def _check_address(self) -> str:
        if not configured():
            raise VaultNotConfigured("Vault is not configured on this gateway")
        address = settings.VAULT_ADDR.rstrip("/")
        if address.startswith("http://") and not settings.VAULT_ALLOW_INSECURE_HTTP:
            raise VaultError("Vault must be reached over https")
        if not address.startswith(("https://", "http://")):
            raise VaultError("VAULT_ADDR must start with https://")
        return address

    def _client(self) -> httpx.AsyncClient:
        headers = {"X-Vault-Namespace": settings.VAULT_NAMESPACE} if settings.VAULT_NAMESPACE else {}
        return httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, transport=self._transport, headers=headers, follow_redirects=False)

    async def _auth_token(self, client: httpx.AsyncClient, address: str) -> str:
        if settings.VAULT_TOKEN:
            return settings.VAULT_TOKEN
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        try:
            response = await client.post(
                f"{address}/v1/auth/approle/login", json={"role_id": settings.VAULT_ROLE_ID, "secret_id": settings.VAULT_SECRET_ID}
            )
        except httpx.HTTPError as exc:
            raise VaultError(f"could not reach Vault to log in ({type(exc).__name__})") from None
        if response.status_code != 200:
            raise VaultError(f"Vault refused the AppRole login (HTTP {response.status_code})")
        auth = (response.json() or {}).get("auth") or {}
        token = auth.get("client_token")
        if not token:
            raise VaultError("Vault's AppRole login returned no token")
        self._token = token
        self._token_expires = time.monotonic() + max(int(auth.get("lease_duration") or 0) - TOKEN_REFRESH_MARGIN_SECONDS, 0)
        return token

    async def read(self, org_id: uuid.UUID, path: str, field: str | None = None) -> str:
        field = field or DEFAULT_FIELD
        try:
            validate_path(org_id, path, field)
        except ValueError as exc:
            raise VaultError(str(exc)) from None
        cache_key = (path, field)
        cached = self._secrets.get(cache_key)
        if cached and time.monotonic() < cached.expires:
            return cached.value
        address = self._check_address()
        async with self._client() as client:
            token = await self._auth_token(client, address)
            try:
                response = await client.get(f"{address}/v1/{settings.VAULT_KV_MOUNT}/data/{path}", headers={"X-Vault-Token": token})
            except httpx.HTTPError as exc:
                raise VaultError(f"could not reach Vault ({type(exc).__name__})") from None
        if response.status_code != 200:
            raise VaultError(f"Vault could not give the secret (HTTP {response.status_code})")
        data = ((response.json() or {}).get("data") or {}).get("data") or {}
        value = data.get(field)
        if not isinstance(value, str) or not value:
            raise VaultError(f"the secret has no '{field}' field")
        self._secrets[cache_key] = _Cached(value, time.monotonic() + settings.VAULT_CACHE_SECONDS)
        return value

    def forget(self) -> None:
        """Drop everything cached (a test, or after changing the configuration)."""
        self._secrets.clear()
        self._token, self._token_expires = None, 0.0


vault_client = VaultClient()
