"""The one place a provider key's secret is read: stored encrypted, or fetched from Vault or AWS Secrets Manager."""

from __future__ import annotations

from app.models.llm_provider_key import LLMProviderKey
from app.services.aws_secrets import aws_secrets
from app.services.crypto_service import decrypt
from app.services.external_secret_error import ExternalSecretError
from app.services.vault_client import VaultError, vault_client

VAULT, AWS = "vault", "aws"
EXTERNAL = (VAULT, AWS)


def is_vault_backed(key: LLMProviderKey) -> bool:
    return getattr(key, "secret_source", "local") == VAULT


def is_external(key: LLMProviderKey) -> bool:
    """The secret is not stored here: the gateway holds a reference and reads it when a request needs it."""
    return getattr(key, "secret_source", "local") in EXTERNAL


async def resolve_secret(key: LLMProviderKey) -> str:
    """The key's secret. Raises ``ValueError`` (stored, undecryptable) or ``ExternalSecretError`` (Vault / AWS); never falls back from one source to another."""
    source = getattr(key, "secret_source", "local")
    if source == VAULT:
        return await vault_client.read(key.org_id, key.vault_path or "", key.vault_field)
    if source == AWS:
        return await aws_secrets.read(key.org_id, key.vault_path or "", key.vault_field)
    return decrypt(key.api_key_encrypted or "")


def display_label(key: LLMProviderKey) -> str:
    """What the console shows in place of a key prefix. An external key has no prefix to show, only where it comes from."""
    source = getattr(key, "secret_source", "local")
    return f"{source}:{key.vault_path}" if source in EXTERNAL else ""


__all__ = ["ExternalSecretError", "VaultError", "display_label", "is_external", "is_vault_backed", "resolve_secret"]
