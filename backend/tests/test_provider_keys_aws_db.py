"""AWS-backed provider keys against the real schema: creation rules, listing, rotation, selection."""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.database import org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.llm_provider_key import LLMProviderKey
from app.services import aws_secrets as aws
from app.services import key_secrets
from app.services.llm_service import llm_service
from tests.db_helpers import Api, remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/provider-keys"
SECRET = "sk-from-aws-abcdefgh"


@pytest.fixture
def secrets(monkeypatch):
	"""AWS Secrets Manager faked at the client: serves one value, records what it is asked for, and can be taken down."""
	for name, value in dict(AWS_SECRETS_ENABLED=True, AWS_SECRET_PREFIX="openproxyai/{org_id}/", AWS_SECRET_CACHE_SECONDS=0).items():
		monkeypatch.setattr(settings, name, value)
	seen = type("Seen", (), {"names": [], "down": False})()

	class Fake:
		def get_secret_value(self, SecretId):  # noqa: N803
			seen.names.append(SecretId)
			if seen.down:
				raise ConnectionError("down")
			return {"SecretString": SECRET}

	client = aws.AwsSecretsClient(client_factory=Fake)
	monkeypatch.setattr(aws, "aws_secrets", client)
	monkeypatch.setattr(key_secrets, "aws_secrets", client)
	return seen


async def create(api, org_id, *, name=None, **extra):
	return await api.http.post(PATH, json={"provider": "openai", "key_alias": "aws-key", "aws_secret_name": name or f"openproxyai/{org_id}/openai", **extra})


async def test_an_aws_key_is_created_listed_without_its_secret_and_audited(tenants, secrets):
	async with Api(tenants.a, tenants.user_a) as api:
		created = await create(api, tenants.a)
		assert created.status_code == 201, created.text
		body = created.json()
		assert body["secret_source"] == "aws" and body["key_prefix"] == f"aws:openproxyai/{tenants.a}/openai"
		assert SECRET not in json.dumps(body) and SECRET not in (await api.http.get(PATH)).text
	assert len(secrets.names) == 1  # read once to prove it is readable; listing did not ask AWS again
	async with org_scoped_session(tenants.a) as db:
		row = (await db.scalars(select(LLMProviderKey).where(LLMProviderKey.org_id == tenants.a))).one()
		audit = [r.after for r in await db.scalars(select(AdminAuditLog).where(AdminAuditLog.org_id == tenants.a, AdminAuditLog.action == "provider_key.created"))]
	assert row.api_key_encrypted is None and row.secret_source == "aws" and SECRET not in json.dumps(audit, default=str)


async def test_a_name_in_another_orgs_folder_or_an_arn_is_refused_and_aws_is_never_asked(tenants, secrets):
	async with Api(tenants.a, tenants.user_a) as api:
		for name in (f"openproxyai/{tenants.b}/openai", f"openproxyai/{tenants.a}/../{tenants.b}/x", "prod/anything", f"arn:aws:secretsmanager:us-east-1:1:secret:openproxyai/{tenants.a}/x"):
			response = await create(api, tenants.a, name=name)
			assert response.status_code == 422 and response.json()["detail"]["error"] == "invalid_aws_secret", (name, response.text)
	assert secrets.names == []


async def test_a_key_needs_exactly_one_source(tenants, secrets):
	async with Api(tenants.a, tenants.user_a) as api:
		both = await api.http.post(PATH, json={"provider": "openai", "key_alias": "x", "api_key": "sk-abcdefghij", "aws_secret_name": f"openproxyai/{tenants.a}/k"})
		two_managers = await api.http.post(PATH, json={"provider": "openai", "key_alias": "x", "vault_path": f"openproxyai/{tenants.a}/k", "aws_secret_name": f"openproxyai/{tenants.a}/k"})
		stray = await api.http.post(PATH, json={"provider": "openai", "key_alias": "x", "api_key": "sk-abcdefghij", "aws_secret_field": "f"})
		assert [both.status_code, two_managers.status_code, stray.status_code] == [422, 422, 422]


async def test_creation_says_so_when_aws_is_not_enabled_or_the_secret_cannot_be_read(tenants, secrets, monkeypatch):
	async with Api(tenants.a, tenants.user_a) as api:
		secrets.down = True
		down = await create(api, tenants.a)
		assert down.status_code == 422 and down.json()["detail"]["error"] == "aws_unreadable"
		monkeypatch.setattr(settings, "AWS_SECRETS_ENABLED", False)
		off = await create(api, tenants.a)
		assert off.status_code == 422 and off.json()["detail"]["error"] == "aws_not_configured"


async def test_an_aws_key_is_rotated_in_aws_not_here(tenants, secrets):
	async with Api(tenants.a, tenants.user_a) as api:
		key_id = (await create(api, tenants.a)).json()["id"]
		response = await api.http.post(f"{PATH}/{key_id}/rotate")
		assert response.status_code == 409 and response.json()["detail"]["error"] == "vault_backed_key"


async def test_a_request_uses_the_secret_read_from_aws_and_an_outage_is_a_503_never_another_source(tenants, secrets):
	async with Api(tenants.a, tenants.user_a) as api:
		await create(api, tenants.a)
	async with org_scoped_session(tenants.a) as db:
		candidates = await llm_service._select_provider_keys(db, tenants.a, "openai", model="gpt-4o", max_attempts=0)
	assert [c.api_key for c in candidates] == [SECRET]
	secrets.down = True
	async with org_scoped_session(tenants.a) as db:
		with pytest.raises(HTTPException) as caught:
			await llm_service._select_provider_keys(db, tenants.a, "openai", model="gpt-4o", max_attempts=0)
	assert caught.value.status_code == 503 and "secret manager" in str(caught.value.detail)


async def test_the_database_allows_aws_and_still_refuses_a_key_with_both_sources_or_neither(tenants, secrets):
	async with org_scoped_session(tenants.a) as db:
		db.add(LLMProviderKey(org_id=tenants.a, provider="openai", key_alias="both", secret_source="aws", api_key_encrypted="x", vault_path="p"))
		with pytest.raises(Exception, match="ck_llm_provider_keys_secret_source"):
			await db.commit()
	async with org_scoped_session(tenants.a) as db:
		db.add(LLMProviderKey(org_id=tenants.a, provider="openai", key_alias="ok", secret_source="aws", api_key_encrypted=None, vault_path=f"openproxyai/{tenants.a}/k"))
		await db.commit()
