"""Model registry against the real schema: RLS, constraints, key linkage and the admin API."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from app.database import org_scoped_session
from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.models.llm_provider_key import LLMProviderKey
from app.models.model_registry import ModelRegistryEntry
from app.services.crypto_service import encrypt
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/model-registry"


async def make_key(org_id, provider="openai", max_data_class="internal") -> uuid.UUID:
	async with org_scoped_session(org_id) as db:
		key = LLMProviderKey(
			org_id=org_id, provider=provider, key_alias=f"k-{uuid.uuid4().hex[:6]}", api_key_encrypted=encrypt("sk-test-key-12345"),
			region="global", max_data_class=max_data_class,
		)
		db.add(key)
		await db.commit()
		return key.id


def body(**overrides) -> dict:
	return {"model_id": "openai/gpt-4o", "regions": ["us"], **overrides}


class Api:
	"""The app with the caller pinned to an org and role, talking to the real database."""

	def __init__(self, tenants, role="admin"):
		self.user = tenants.user_a
		self.user.role = role
		self.org = tenants.a

	async def __aenter__(self):
		async def fake_user():
			return self.user

		async def scoped_db():
			async with org_scoped_session(self.org) as session:
				yield session

		app.dependency_overrides[get_current_user_from_jwt] = fake_user
		app.dependency_overrides[get_db] = scoped_db
		self.http = AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test")
		return self

	async def __aexit__(self, *exc):
		await self.http.aclose()
		app.dependency_overrides.clear()


async def test_crud_flow(tenants):
	key = await make_key(tenants.a)
	async with Api(tenants) as api:
		created = await api.http.post(PATH, json=body(provider_key_id=str(key), capabilities=["CODE_GENERATION"], owner="platform", retention_days=30))
		assert created.status_code == 201, created.text
		entry = created.json()
		assert entry["provider"] == "openai" and entry["provider_key_id"] == str(key)
		assert entry["max_data_class"] == "internal" and entry["enabled"] is True and entry["capabilities"] == ["CODE_GENERATION"]

		assert (await api.http.get(PATH)).json()[0]["id"] == entry["id"]
		assert (await api.http.get(f"{PATH}/{entry['id']}")).json()["model_id"] == "openai/gpt-4o"

		patched = await api.http.patch(f"{PATH}/{entry['id']}", json={"enabled": False, "risk_rating": "high", "regions": ["eu", "us"]})
		assert patched.json()["enabled"] is False and patched.json()["risk_rating"] == "high" and patched.json()["regions"] == ["eu", "us"]
		assert (await api.http.patch(f"{PATH}/{entry['id']}", json={})).status_code == 422
		assert (await api.http.patch(f"{PATH}/{entry['id']}", json={"model_id": "openai/other"})).status_code == 422

		assert (await api.http.delete(f"{PATH}/{entry['id']}")).status_code == 204
		assert (await api.http.get(PATH)).json() == []
		assert (await api.http.delete(f"{PATH}/{uuid.uuid4()}")).status_code == 404
		assert (await api.http.get(f"{PATH}/{uuid.uuid4()}")).status_code == 404


async def test_duplicate_model_in_one_org_is_a_conflict(tenants):
	async with Api(tenants) as api:
		assert (await api.http.post(PATH, json=body())).status_code == 201
		assert (await api.http.post(PATH, json=body())).status_code == 409


async def test_only_admins_can_use_the_registry(tenants):
	async with Api(tenants, role="developer") as api:
		assert (await api.http.get(PATH)).status_code == 403
		assert (await api.http.post(PATH, json=body())).status_code == 403
		assert (await api.http.patch(f"{PATH}/{uuid.uuid4()}", json={"enabled": False})).status_code == 403
		assert (await api.http.delete(f"{PATH}/{uuid.uuid4()}")).status_code == 403


async def test_key_must_exist_in_this_org_and_match_the_provider(tenants):
	foreign_key = await make_key(tenants.b)
	anthropic_key = await make_key(tenants.a, provider="anthropic")
	async with Api(tenants) as api:
		assert (await api.http.post(PATH, json=body(provider_key_id=str(foreign_key)))).status_code == 422  # org B's key is invisible
		assert (await api.http.post(PATH, json=body(provider_key_id=str(uuid.uuid4())))).status_code == 422
		mismatch = await api.http.post(PATH, json=body(provider_key_id=str(anthropic_key)))
		assert mismatch.status_code == 422 and "provider" in mismatch.json()["detail"]["detail"]


async def test_a_model_cannot_be_cleared_for_more_than_its_key(tenants):
	key = await make_key(tenants.a, max_data_class="internal")
	async with Api(tenants) as api:
		too_high = await api.http.post(PATH, json=body(provider_key_id=str(key), max_data_class="confidential"))
		assert too_high.status_code == 422 and "data class" in too_high.json()["detail"]["detail"]
		assert (await api.http.post(PATH, json=body(provider_key_id=str(key), max_data_class="internal"))).status_code == 201

		entry = (await api.http.get(PATH)).json()[0]
		assert (await api.http.patch(f"{PATH}/{entry['id']}", json={"max_data_class": "secret"})).status_code == 422
		assert (await api.http.patch(f"{PATH}/{entry['id']}", json={"max_data_class": "public"})).status_code == 200


async def test_attaching_a_key_on_update_is_validated_too(tenants):
	anthropic_key = await make_key(tenants.a, provider="anthropic")
	async with Api(tenants) as api:
		entry = (await api.http.post(PATH, json=body())).json()
		assert (await api.http.patch(f"{PATH}/{entry['id']}", json={"provider_key_id": str(anthropic_key)})).status_code == 422
		good = await make_key(tenants.a)
		assert (await api.http.patch(f"{PATH}/{entry['id']}", json={"provider_key_id": str(good)})).json()["provider_key_id"] == str(good)
		assert (await api.http.patch(f"{PATH}/{entry['id']}", json={"provider_key_id": None})).json()["provider_key_id"] is None


async def test_deleting_the_key_detaches_the_entry_instead_of_deleting_it(tenants):
	key = await make_key(tenants.a)
	async with Api(tenants) as api:
		entry = (await api.http.post(PATH, json=body(provider_key_id=str(key)))).json()
	async with org_scoped_session(tenants.a) as db:
		await db.delete(await db.get(LLMProviderKey, key))
		await db.commit()
	async with Api(tenants) as api:
		kept = (await api.http.get(f"{PATH}/{entry['id']}")).json()
		assert kept["provider_key_id"] is None  # not routable until an admin attaches another key


async def test_rls_hides_other_orgs_entries(tenants):
	async with org_scoped_session(tenants.a) as db:
		db.add(ModelRegistryEntry(org_id=tenants.a, model_id="openai/gpt-4o", provider="openai", regions=["us"]))
		await db.commit()
	async with org_scoped_session(tenants.b) as db:
		assert await db.scalar(select(func.count()).select_from(ModelRegistryEntry)) == 0
		db.add(ModelRegistryEntry(org_id=tenants.b, model_id="openai/gpt-4o", provider="openai", regions=["eu"]))  # same name is fine in another org
		await db.commit()
	async with org_scoped_session(tenants.a) as db:
		assert await db.scalar(select(func.count()).select_from(ModelRegistryEntry)) == 1


async def test_database_rejects_rows_for_another_org_and_bad_enums(tenants):
	with pytest.raises(DBAPIError):
		async with org_scoped_session(tenants.a) as db:
			db.add(ModelRegistryEntry(org_id=tenants.b, model_id="openai/x", provider="openai", regions=["us"]))
			await db.commit()
	with pytest.raises(DBAPIError):
		async with org_scoped_session(tenants.a) as db:
			db.add(ModelRegistryEntry(org_id=tenants.a, model_id="openai/y", provider="openai", regions=["us"], risk_rating="extreme"))
			await db.commit()
	with pytest.raises(DBAPIError):
		async with org_scoped_session(tenants.a) as db:
			db.add(ModelRegistryEntry(org_id=tenants.a, model_id="openai/z", provider="openai", regions=["us"], max_data_class="nope"))
			await db.commit()
