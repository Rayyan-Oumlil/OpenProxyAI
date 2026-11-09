"""Loading routing candidates from the real schema: the registry joined with its keys, scoped by RLS."""

from __future__ import annotations

import uuid

from app.database import org_scoped_session
from app.models.llm_provider_key import LLMProviderKey
from app.models.model_registry import ModelRegistryEntry
from app.services.crypto_service import encrypt
from app.services.routing_service import authorize, load_candidates
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


async def add_key(org_id, *, active=True, max_data_class="confidential") -> uuid.UUID:
	async with org_scoped_session(org_id) as db:
		key = LLMProviderKey(
			org_id=org_id, provider="openai", key_alias=f"k-{uuid.uuid4().hex[:6]}", api_key_encrypted=encrypt("sk-test-key-12345"),
			region="global", is_active=active, max_data_class=max_data_class,
		)
		db.add(key)
		await db.commit()
		return key.id


async def add_entry(org_id, model_id, key_id=None, **fields) -> None:
	async with org_scoped_session(org_id) as db:
		db.add(ModelRegistryEntry(org_id=org_id, model_id=model_id, provider=model_id.split("/")[0], provider_key_id=key_id, regions=["us"], **fields))
		await db.commit()


async def test_candidates_join_entries_with_their_keys(tenants):
	key = await add_key(tenants.a, max_data_class="internal")
	await add_entry(tenants.a, "openai/gpt-4o", key, max_data_class="confidential", capabilities=["VISION"], cost_tier="low")
	await add_entry(tenants.a, "openai/detached")  # no key attached

	async with org_scoped_session(tenants.a) as db:
		loaded = {c.model_id: c for c in await load_candidates(db, tenants.a)}

	attached, detached = loaded["openai/gpt-4o"], loaded["openai/detached"]
	assert (attached.key_id, attached.key_active, attached.key_class, attached.entry_class) == (key, True, "internal", "confidential")
	assert attached.capabilities == ("VISION",) and attached.cost_tier == "low" and attached.regions == ("us",)
	assert (detached.key_id, detached.key_active, detached.key_class) == (None, False, None)


async def test_loaded_candidates_feed_the_rules_end_to_end(tenants):
	key = await add_key(tenants.a, max_data_class="internal")
	await add_entry(tenants.a, "openai/gpt-4o", key, max_data_class="confidential")  # cleared higher than its key
	inactive = await add_key(tenants.a, active=False)
	await add_entry(tenants.a, "openai/off", inactive, max_data_class="secret")

	async with org_scoped_session(tenants.a) as db:
		candidates = await load_candidates(db, tenants.a)
	result = authorize(candidates, data_class="confidential", org_region="us", max_risk="high", allows_model=lambda _m: True)
	assert result.excluded == {"openai/gpt-4o": "class_too_low", "openai/off": "key_inactive"}  # the key's lower class wins
	assert authorize(candidates, data_class="internal", org_region="us", max_risk="high", allows_model=lambda _m: True).excluded == {"openai/off": "key_inactive"}


async def test_another_orgs_registry_is_invisible(tenants):
	await add_entry(tenants.b, "openai/theirs")
	await add_entry(tenants.a, "openai/ours")
	async with org_scoped_session(tenants.a) as db:
		assert [c.model_id for c in await load_candidates(db, tenants.a)] == ["openai/ours"]
