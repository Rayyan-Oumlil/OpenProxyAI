"""Vault-backed provider keys against the real schema: creation rules, listing, rotation, selection (Phase 5, slice 5.10)."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.database import org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.llm_provider_key import LLMProviderKey
from app.services import key_secrets
from app.services import vault_client as vc
from app.services.llm_service import llm_service
from tests.db_helpers import Api, remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/provider-keys"
SECRET = "sk-from-vault-abcdefgh"


@pytest.fixture
def vault(monkeypatch):
	"""A configured Vault that serves one secret per org folder, and records what it is asked for."""
	for name, value in dict(VAULT_ADDR="https://vault.example", VAULT_TOKEN="s.t", VAULT_ROLE_ID="", VAULT_SECRET_ID="", VAULT_NAMESPACE="", VAULT_CACHE_SECONDS=0).items():
		monkeypatch.setattr(settings, name, value)
	seen = type("Seen", (), {"paths": [], "down": False})()

	def handler(request):
		seen.paths.append(request.url.path)
		if seen.down:
			return httpx.Response(503, json={"errors": ["sealed"]})
		return httpx.Response(200, json={"data": {"data": {"api_key": SECRET}}})

	client = vc.VaultClient(transport=httpx.MockTransport(handler))
	monkeypatch.setattr(vc, "vault_client", client)
	monkeypatch.setattr(key_secrets, "vault_client", client)
	return seen


async def create(api, org_id, *, path=None, **body):
	return await api.http.post(PATH, json={"provider": "openai", "key_alias": "vaulted", "vault_path": path or f"openproxyai/{org_id}/openai", **body})


async def test_a_vault_key_is_created_listed_without_its_secret_and_audited(tenants, vault):
	async with Api(tenants.a, tenants.user_a) as api:
		created = await create(api, tenants.a, vault_field="api_key")
		assert created.status_code == 201, created.text
		body = created.json()
		assert body["secret_source"] == "vault" and body["vault_path"] == f"openproxyai/{tenants.a}/openai"
		assert body["key_prefix"] == f"vault:openproxyai/{tenants.a}/openai"
		assert SECRET not in json.dumps(body)
		listed = (await api.http.get(PATH)).json()
		assert SECRET not in json.dumps(listed) and listed[0]["secret_source"] == "vault"
	assert len(vault.paths) == 1  # read once, to prove it is readable; listing did not ask Vault again
	async with org_scoped_session(tenants.a) as db:
		row = (await db.scalars(select(LLMProviderKey).where(LLMProviderKey.org_id == tenants.a))).one()
		assert row.api_key_encrypted is None and row.vault_path.endswith("/openai")
		audit = [r.after for r in (await db.scalars(select(AdminAuditLog).where(AdminAuditLog.org_id == tenants.a, AdminAuditLog.action == "provider_key.created")))]
	assert audit and SECRET not in json.dumps(audit, default=str) and audit[0]["vault_path"].endswith("/openai")


async def test_a_path_in_another_orgs_folder_is_refused_and_vault_is_never_asked(tenants, vault):
	async with Api(tenants.a, tenants.user_a) as api:
		for path in (f"openproxyai/{tenants.b}/openai", f"openproxyai/{tenants.a}/../{tenants.b}/openai", "secret/anything", f"openproxyai/{tenants.a}"):
			response = await create(api, tenants.a, path=path)
			assert response.status_code == 422 and response.json()["detail"]["error"] == "invalid_vault_path", (path, response.text)
	assert vault.paths == []


async def test_a_key_needs_exactly_one_source(tenants, vault):
	async with Api(tenants.a, tenants.user_a) as api:
		both = await api.http.post(PATH, json={"provider": "openai", "key_alias": "x", "api_key": "sk-abcdefghij", "vault_path": f"openproxyai/{tenants.a}/k"})
		neither = await api.http.post(PATH, json={"provider": "openai", "key_alias": "x"})
		stray_field = await api.http.post(PATH, json={"provider": "openai", "key_alias": "x", "api_key": "sk-abcdefghij", "vault_field": "f"})
		assert [both.status_code, neither.status_code, stray_field.status_code] == [422, 422, 422]


async def test_a_secret_that_cannot_be_read_now_is_refused_at_creation(tenants, vault):
	vault.down = True
	async with Api(tenants.a, tenants.user_a) as api:
		response = await create(api, tenants.a)
		assert response.status_code == 422 and response.json()["detail"]["error"] == "vault_unreadable" and "sealed" not in response.text


async def test_creation_says_so_when_vault_is_not_configured_on_the_gateway(tenants, vault, monkeypatch):
	monkeypatch.setattr(settings, "VAULT_ADDR", "")
	async with Api(tenants.a, tenants.user_a) as api:
		response = await create(api, tenants.a)
		assert response.status_code == 422 and response.json()["detail"]["error"] == "vault_not_configured"


async def test_a_vault_key_is_rotated_in_vault_not_here(tenants, vault):
	async with Api(tenants.a, tenants.user_a) as api:
		key_id = (await create(api, tenants.a)).json()["id"]
		response = await api.http.post(f"{PATH}/{key_id}/rotate")
		assert response.status_code == 409 and response.json()["detail"]["error"] == "vault_backed_key"


async def test_the_database_refuses_a_key_with_both_sources_or_neither(tenants, vault):
	async with org_scoped_session(tenants.a) as db:
		db.add(LLMProviderKey(org_id=tenants.a, provider="openai", key_alias="both", secret_source="vault", api_key_encrypted="x", vault_path="p"))
		with pytest.raises(Exception, match="ck_llm_provider_keys_secret_source"):
			await db.commit()
	async with org_scoped_session(tenants.a) as db:
		db.add(LLMProviderKey(org_id=tenants.a, provider="openai", key_alias="neither", secret_source="local", api_key_encrypted=None))
		with pytest.raises(Exception, match="ck_llm_provider_keys_secret_source"):
			await db.commit()


async def test_a_request_uses_the_secret_read_from_vault_for_that_request(tenants, vault):
	async with Api(tenants.a, tenants.user_a) as api:
		await create(api, tenants.a)
	async with org_scoped_session(tenants.a) as db:
		candidates = await llm_service._select_provider_keys(db, tenants.a, "openai", model="gpt-4o", max_attempts=0)
	assert [c.api_key for c in candidates] == [SECRET]


async def test_a_vault_outage_is_a_503_for_the_request_and_never_another_source(tenants, vault):
	async with Api(tenants.a, tenants.user_a) as api:
		await create(api, tenants.a)
	vault.down = True
	async with org_scoped_session(tenants.a) as db:
		with pytest.raises(HTTPException) as caught:
			await llm_service._select_provider_keys(db, tenants.a, "openai", model="gpt-4o", max_attempts=0)
	assert caught.value.status_code == 503 and "Vault" in str(caught.value.detail) and "sealed" not in str(caught.value.detail)


async def test_a_stored_key_beside_a_broken_vault_key_still_serves_but_a_vault_key_is_never_substituted(tenants, vault):
	"""An unreadable Vault key is skipped (and logged); the org's other key keeps working. The reverse never happens."""
	async with Api(tenants.a, tenants.user_a) as api:
		await create(api, tenants.a)
		stored = await api.http.post(PATH, json={"provider": "openai", "key_alias": "plain", "api_key": "sk-stored-abcdefgh"})
		assert stored.status_code == 201
	vault.down = True
	async with org_scoped_session(tenants.a) as db:
		candidates = await llm_service._select_provider_keys(db, tenants.a, "openai", model="gpt-4o", max_attempts=5)
	assert [c.api_key for c in candidates] == ["sk-stored-abcdefgh"]
