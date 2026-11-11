"""The one place a provider key's secret is read (Phase 5, slice 5.10): stored encrypted, or fetched from Vault."""

from __future__ import annotations

from app.models.llm_provider_key import LLMProviderKey
from app.services.crypto_service import decrypt
from app.services.vault_client import VaultError, vault_client

VAULT = "vault"


def is_vault_backed(key: LLMProviderKey) -> bool:
    return getattr(key, "secret_source", "local") == VAULT


async def resolve_secret(key: LLMProviderKey) -> str:
    """The key's secret. Raises ``ValueError`` (stored, undecryptable) or ``VaultError`` (Vault); never falls back from one to the other."""
    if is_vault_backed(key):
        return await vault_client.read(key.org_id, key.vault_path or "", key.vault_field)
    return decrypt(key.api_key_encrypted or "")


def display_label(key: LLMProviderKey) -> str:
    """What the console shows in place of a key prefix. A Vault key has no prefix to show, only where it comes from."""
    return f"vault:{key.vault_path}" if is_vault_backed(key) else ""


__all__ = ["VaultError", "display_label", "is_vault_backed", "resolve_secret"]
