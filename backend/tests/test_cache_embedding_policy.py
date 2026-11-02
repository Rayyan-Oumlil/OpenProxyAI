"""Semantic cache must never call an outside embedding model implicitly, and never share entries across orgs."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import cache_service


def _db_for(region: str) -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=SimpleNamespace(data_region=region))
    result = MagicMock()
    result.one_or_none = lambda: None
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    return r


async def _l3_get(mock_redis, db, query: str):
    return await cache_service.get(
        mock_redis,
        "gpt-4",
        [{"role": "user", "content": query}],
        0.1,
        org_id=uuid.uuid4(),
        db=db,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "region,airgap,api_key,api_base",
    [
        ("us", False, "", ""),  # no explicit embedding config
        ("eu", False, "sk-embed", ""),  # region not allowed to use the shared endpoint
        ("us", True, "sk-embed", ""),  # air-gapped
    ],
)
async def test_l3_skips_embedding_call(mock_redis, region, airgap, api_key, api_base):
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", False),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", True),
        patch.object(settings, "AIRGAP_MODE", airgap),
        patch.object(settings, "SEMANTIC_CACHE_EMBEDDING_API_KEY", api_key),
        patch.object(settings, "SEMANTIC_CACHE_EMBEDDING_API_BASE", api_base),
        patch("litellm.aembedding", new_callable=AsyncMock) as mock_emb,
    ):
        result, tier = await _l3_get(mock_redis, _db_for(region), f"q-{uuid.uuid4()}")

    assert (result, tier) == (None, None)
    mock_emb.assert_not_called()


@pytest.mark.asyncio
async def test_l3_embeds_with_explicit_credentials(mock_redis):
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", False),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", True),
        patch.object(settings, "AIRGAP_MODE", False),
        patch.object(settings, "SEMANTIC_CACHE_EMBEDDING_API_KEY", "sk-embed"),
        patch.object(settings, "SEMANTIC_CACHE_EMBEDDING_API_BASE", "https://embed.internal/v1"),
        patch("litellm.aembedding", new_callable=AsyncMock) as mock_emb,
    ):
        mock_emb.return_value = MagicMock(data=[MagicMock(embedding=[0.1] * 4)])
        await _l3_get(mock_redis, _db_for("us"), f"q-{uuid.uuid4()}")

    mock_emb.assert_awaited_once()
    kwargs = mock_emb.await_args.kwargs
    assert kwargs["api_key"] == "sk-embed"
    assert kwargs["api_base"] == "https://embed.internal/v1"
    assert kwargs["model"] == settings.SEMANTIC_CACHE_EMBEDDING_MODEL


@pytest.mark.asyncio
async def test_set_l3_skips_embedding_without_config(monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_CACHE_EMBEDDING_API_KEY", "")
    monkeypatch.setattr(settings, "SEMANTIC_CACHE_EMBEDDING_API_BASE", "")
    org_session = MagicMock()
    org_session.__aenter__ = AsyncMock(return_value=SimpleNamespace(get=AsyncMock(return_value=None)))
    org_session.__aexit__ = AsyncMock(return_value=False)
    with (
        patch("app.database.org_scoped_session", return_value=org_session),
        patch("litellm.aembedding", new_callable=AsyncMock) as mock_emb,
    ):
        await cache_service._set_l3_semantic(
            uuid.uuid4(), "gpt-4", [{"role": "user", "content": "hi"}], {"ok": True}, 1, 60
        )
    mock_emb.assert_not_called()


def test_exact_cache_key_is_scoped_by_org():
    messages = [{"role": "user", "content": "same prompt"}]
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    key_a = cache_service._make_key("gpt-4", messages, 0.0, org_a)
    assert key_a != cache_service._make_key("gpt-4", messages, 0.0, org_b)
    assert key_a == cache_service._make_key("gpt-4", messages, 0.0, org_a)


@pytest.mark.asyncio
async def test_l2_hit_does_not_cross_orgs(mock_redis):
    """A response cached for org A is not served to org B for an identical prompt."""
    store: dict[str, str] = {}
    mock_redis.get = AsyncMock(side_effect=lambda k: store.get(k))
    mock_redis.setex = AsyncMock(side_effect=lambda k, ttl, v: store.__setitem__(k, v))
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    messages = [{"role": "user", "content": f"shared-{uuid.uuid4()}"}]
    body = {"choices": [{"message": {"content": "answer for org A"}}], "usage": {"total_tokens": 3}}

    with (
        patch.object(settings, "CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", False),
    ):
        await cache_service.set(mock_redis, "gpt-4", messages, 0.0, body, org_id=org_a)
        hit_a, _ = await cache_service.get(mock_redis, "gpt-4", messages, 0.0, org_id=org_a)
        hit_b, tier_b = await cache_service.get(mock_redis, "gpt-4", messages, 0.0, org_id=org_b)

    assert hit_a == body
    assert (hit_b, tier_b) == (None, None)
