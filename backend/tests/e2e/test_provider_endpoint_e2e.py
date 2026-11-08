"""A provider key with its own api_base sends chat, streaming and embedding calls there (Phase 2, S1)."""

import json
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import text

from app.config import settings
from app.utils import provider_endpoint
from tests.e2e.conftest import _run, upstream_calls
from tests.fakes.fake_openai import FakeUpstream

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"
EMBED = "/v1/embeddings"


@pytest.fixture(scope="module")
def custom_endpoint() -> Generator[FakeUpstream, None, None]:
    """A second upstream, standing in for a private vLLM or a regional gateway."""
    server = FakeUpstream()
    server.start()
    yield server
    server.stop()


@pytest.fixture(autouse=True)
def _reset_custom_endpoint(custom_endpoint: FakeUpstream) -> None:
    httpx.post(f"{custom_endpoint.base_url.removesuffix('/v1')}/__reset")
    provider_endpoint.clear_runtime_cache()


@pytest.fixture
def internal_endpoints_enabled(monkeypatch) -> None:
    """The operator switch a self-hosted deployment turns on to use a private vLLM."""
    monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)


def _point_keys_at(org_id, api_base: str) -> None:
    async def update(session) -> None:
        await session.execute(
            text("UPDATE llm_provider_keys SET api_base = :b, is_internal = true WHERE org_id = :o"),
            {"b": api_base, "o": org_id},
        )
        await session.commit()

    _run(update)


def _body(content: str = "hello", **extra):
    return {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": content}], **extra}


def test_chat_goes_to_the_keys_endpoint_not_the_default_one(e2e_client, upstream, custom_endpoint, make_tenant, internal_endpoints_enabled):
    tenant = make_tenant()
    _point_keys_at(tenant.org_id, custom_endpoint.base_url)

    response = e2e_client.post(CHAT, json=_body("ping"), headers=tenant.headers)

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "echo: ping"
    assert upstream_calls(upstream) == []
    [call] = upstream_calls(custom_endpoint)
    assert call["authorization"] == "Bearer sk-good"


def test_streaming_goes_to_the_keys_endpoint(e2e_client, upstream, custom_endpoint, make_tenant, internal_endpoints_enabled):
    tenant = make_tenant()
    _point_keys_at(tenant.org_id, custom_endpoint.base_url)

    with e2e_client.stream("POST", CHAT, json=_body("stream me", stream=True), headers=tenant.headers) as response:
        assert response.status_code == 200
        events = [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ") and line != "data: [DONE]"]

    text = "".join(choice["delta"].get("content") or "" for event in events for choice in event.get("choices", []))
    assert text == "echo: stream me"
    assert upstream_calls(upstream) == []
    assert len(upstream_calls(custom_endpoint)) == 1


def test_embeddings_go_to_the_keys_endpoint(e2e_client, upstream, custom_endpoint, make_tenant, internal_endpoints_enabled):
    tenant = make_tenant()
    _point_keys_at(tenant.org_id, custom_endpoint.base_url)

    response = e2e_client.post(EMBED, json={"model": "openai/text-embedding-3-small", "input": "hi"}, headers=tenant.headers)

    assert response.status_code == 200
    assert upstream_calls(upstream) == []
    assert len(upstream_calls(custom_endpoint)) == 1


def test_a_key_without_api_base_still_uses_the_default_endpoint(e2e_client, upstream, custom_endpoint, make_tenant):
    tenant = make_tenant()

    assert e2e_client.post(CHAT, json=_body(), headers=tenant.headers).status_code == 200

    assert len(upstream_calls(upstream)) == 1
    assert upstream_calls(custom_endpoint) == []


def test_with_the_operator_switch_off_the_key_is_refused_and_nothing_falls_back(e2e_client, upstream, custom_endpoint, make_tenant):
    tenant = make_tenant()
    _point_keys_at(tenant.org_id, custom_endpoint.base_url)  # internal key, but ALLOW_INTERNAL_PROVIDER_ENDPOINTS is off

    response = e2e_client.post(CHAT, json=_body("private data"), headers=tenant.headers)

    assert response.status_code == 503
    assert response.json()["error"] == "no_provider_key"
    assert upstream_calls(upstream) == []  # not even the gateway's default endpoint
    assert upstream_calls(custom_endpoint) == []
