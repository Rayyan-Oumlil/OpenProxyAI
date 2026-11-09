"""Classification-aware routing through the real pipeline (Phase 2, S4b): what is served, by which key, and what is refused."""

import json
import time
import uuid
from typing import Any

import pytest
from sqlalchemy import text

from app.models.llm_provider_key import LLMProviderKey
from app.models.model_registry import ModelRegistryEntry
from app.services.crypto_service import encrypt
from tests.e2e.conftest import _run, upstream_calls

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"
SSN_TEXT = "My SSN is 123-45-6789, please draft the letter."
ROUTE_MODEL = "x-openproxyai-route-model"
ROUTE_REASON = "x-openproxyai-route-reason"


def _body(content: str = "hello", model: str = "openai/gpt-4o-mini", **extra):
    return {"model": model, "messages": [{"role": "user", "content": content}], **extra}


def _tenant(make_tenant, mode: str):
    # log_only policy: SSN text is classified but not blocked by the PII rule, so only routing decides.
    return make_tenant(provider_keys=(), org_settings={"policy": {"enforcement_mode": "log_only", "routing_mode": mode}})


def add_key(org_id, raw: str, *, weight: int = 1, max_class: str = "confidential", active: bool = True) -> uuid.UUID:
    key_id = uuid.uuid4()

    async def insert(session) -> None:
        session.add(LLMProviderKey(
            id=key_id, org_id=org_id, provider="openai", key_alias=f"k-{key_id.hex[:6]}", api_key_encrypted=encrypt(raw),
            weight=weight, region="global", max_data_class=max_class, is_active=active,
        ))
        await session.commit()

    _run(insert)
    return key_id


def add_model(org_id, model_id: str, key_id, *, max_class: str = "confidential", capabilities=(), cost_tier=None, enabled: bool = True) -> None:
    async def insert(session) -> None:
        session.add(ModelRegistryEntry(
            org_id=org_id, model_id=model_id, provider=model_id.split("/")[0], provider_key_id=key_id, max_data_class=max_class,
            regions=["us"], capabilities=list(capabilities), cost_tier=cost_tier, enabled=enabled,
        ))
        await session.commit()

    _run(insert)


def logged_rows(org_id, count: int = 1, timeout: float = 5.0) -> list[dict[str, Any]]:
    async def query(session) -> list[dict[str, Any]]:
        result = await session.execute(
            text("SELECT status_code, error_message, request_metadata FROM request_logs WHERE org_id = :o ORDER BY created_at"), {"o": org_id}
        )
        return [dict(row._mapping) for row in result]

    deadline = time.time() + timeout
    while True:
        rows = _run(query)
        if len(rows) >= count or time.time() > deadline:
            return rows
        time.sleep(0.1)


# ── modes ────────────────────────────────────────────────────────────────────


def test_routing_off_changes_nothing(e2e_client, upstream, make_tenant):
    tenant = make_tenant()
    response = e2e_client.post(CHAT, json=_body(), headers=tenant.headers)
    assert response.status_code == 200
    assert ROUTE_MODEL not in response.headers
    [row] = logged_rows(tenant.org_id)
    assert "routing" not in row["request_metadata"]
    assert "route" not in [stage["name"] for stage in row["request_metadata"]["stages"]]


def test_log_only_records_the_decision_but_serves_the_request_anyway(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "log_only")
    add_key(tenant.org_id, "sk-any")  # an unregistered model is still served, because log_only never refuses

    response = e2e_client.post(CHAT, json=_body(), headers=tenant.headers)

    assert response.status_code == 200 and len(upstream_calls(upstream)) == 1
    assert response.headers[ROUTE_REASON] == "not_in_registry" and response.headers[ROUTE_MODEL] == "none"
    [row] = logged_rows(tenant.org_id)
    assert row["request_metadata"]["routing"]["mode"] == "log_only"
    assert row["request_metadata"]["routing"]["reason"] == "not_in_registry"
    assert "route" in [stage["name"] for stage in row["request_metadata"]["stages"]]


# ── enforce: what is allowed ─────────────────────────────────────────────────


def test_an_authorized_model_is_served_only_by_its_registry_key(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    add_key(tenant.org_id, "sk-public-heavy", weight=100, max_class="public")  # would win almost every draw if keys were chosen freely
    registered = add_key(tenant.org_id, "sk-registered", weight=1, max_class="internal")
    add_model(tenant.org_id, "openai/gpt-4o-mini", registered, max_class="internal")

    for i in range(8):
        response = e2e_client.post(CHAT, json=_body(f"ping {i}"), headers=tenant.headers)
        assert response.status_code == 200, response.text
        assert response.headers[ROUTE_MODEL] == "openai/gpt-4o-mini" and response.headers[ROUTE_REASON] == "authorized"

    assert {call["authorization"] for call in upstream_calls(upstream)} == {"Bearer sk-registered"}


def test_a_request_too_sensitive_for_the_model_is_refused_before_any_upstream_call(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    key = add_key(tenant.org_id, "sk-registered", max_class="internal")
    add_model(tenant.org_id, "openai/gpt-4o-mini", key, max_class="internal")

    response = e2e_client.post(CHAT, json=_body(SSN_TEXT), headers=tenant.headers)  # SSN text is confidential

    assert response.status_code == 446
    body = response.json()
    assert body["error"] == "routing_blocked" and body["reason_code"] == "no_authorized_model"
    assert body["route_reason"] == "not_authorized:class_too_low" and body["data_class"] == "confidential"
    assert response.headers["x-openproxyai-data-class"] == "confidential"
    assert upstream_calls(upstream) == []
    [row] = logged_rows(tenant.org_id)
    assert row["status_code"] == 446 and row["error_message"] == "policy_blocked:no_authorized_model"
    assert row["request_metadata"]["routing"]["reason"] == "not_authorized:class_too_low"
    assert "123-45-6789" not in json.dumps(row["request_metadata"])


def test_the_callers_header_can_make_a_request_too_sensitive_for_the_model(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    key = add_key(tenant.org_id, "sk-registered", max_class="confidential")
    add_model(tenant.org_id, "openai/gpt-4o-mini", key, max_class="internal")

    assert e2e_client.post(CHAT, json=_body(), headers=tenant.headers).status_code == 200
    blocked = e2e_client.post(CHAT, json=_body(), headers={**tenant.headers, "x-openproxy-data-class": "confidential"})
    assert blocked.status_code == 446


def test_a_model_missing_from_the_registry_is_refused(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    key = add_key(tenant.org_id, "sk-registered")
    add_model(tenant.org_id, "openai/gpt-4o", key)

    response = e2e_client.post(CHAT, json=_body(model="openai/gpt-4o-mini"), headers=tenant.headers)

    assert response.status_code == 446 and response.json()["route_reason"] == "not_in_registry"
    assert upstream_calls(upstream) == []


def test_a_model_whose_key_is_inactive_is_refused_not_served_by_another_key(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    add_key(tenant.org_id, "sk-other-key", weight=100)
    dead = add_key(tenant.org_id, "sk-dead", active=False)
    add_model(tenant.org_id, "openai/gpt-4o-mini", dead)

    response = e2e_client.post(CHAT, json=_body(), headers=tenant.headers)

    assert response.status_code == 446 and response.json()["route_reason"] == "not_authorized:key_inactive"
    assert upstream_calls(upstream) == []


# ── capability routing ───────────────────────────────────────────────────────


def test_a_capability_request_is_routed_to_the_cheapest_authorized_model(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    key = add_key(tenant.org_id, "sk-registered")
    add_model(tenant.org_id, "openai/gpt-4o", key, capabilities=["VISION"], cost_tier="high")
    add_model(tenant.org_id, "openai/gpt-4o-mini", key, capabilities=["VISION"], cost_tier="low")
    add_model(tenant.org_id, "openai/gpt-4.1-mini", key, capabilities=["SUMMARIZATION"], cost_tier="low")

    response = e2e_client.post(CHAT, json=_body(model="cap:VISION"), headers=tenant.headers)

    assert response.status_code == 200, response.text
    assert response.headers[ROUTE_MODEL] == "openai/gpt-4o-mini" and response.headers[ROUTE_REASON] == "capability"
    [call] = upstream_calls(upstream)
    assert call["body"]["model"] == "gpt-4o-mini"


def test_a_capability_nobody_authorized_provides_is_refused(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    key = add_key(tenant.org_id, "sk-registered")
    add_model(tenant.org_id, "openai/gpt-4.1-mini", key, capabilities=["SUMMARIZATION"])

    response = e2e_client.post(CHAT, json=_body(model="cap:VISION"), headers=tenant.headers)

    assert response.status_code == 446 and response.json()["route_reason"] == "no_model_with_capability"
    assert upstream_calls(upstream) == []


def test_capability_requests_need_routing_enforced(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "log_only")
    response = e2e_client.post(CHAT, json=_body(model="cap:VISION"), headers=tenant.headers)
    assert response.status_code == 400 and upstream_calls(upstream) == []


# ── fallback closure ─────────────────────────────────────────────────────────


def test_an_authorized_fallback_model_is_used_with_its_own_key(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    bad = add_key(tenant.org_id, "sk-bad")  # the fake upstream answers 429 for this key
    good = add_key(tenant.org_id, "sk-good")
    add_model(tenant.org_id, "openai/gpt-4o", bad)
    add_model(tenant.org_id, "openai/gpt-4o-mini", good)

    response = e2e_client.post(CHAT, json=_body(model="openai/gpt-4o"), headers={**tenant.headers, "x-openproxy-fallback-model": "openai/gpt-4o-mini"})

    assert response.status_code == 200, response.text
    calls = [(c["body"]["model"], c["authorization"]) for c in upstream_calls(upstream)]
    assert calls[-1] == ("gpt-4o-mini", "Bearer sk-good")  # the fallback model, with its own registry key
    assert set(calls[:-1]) == {("gpt-4o", "Bearer sk-bad")}  # LiteLLM may retry the primary a few times first
    [row] = logged_rows(tenant.org_id)
    assert row["request_metadata"]["fallback_model_used"] == "openai/gpt-4o-mini"


def test_a_fallback_model_that_is_not_authorized_is_never_called(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    bad = add_key(tenant.org_id, "sk-bad")
    add_key(tenant.org_id, "sk-good", weight=100)
    add_model(tenant.org_id, "openai/gpt-4o", bad)  # "openai/gpt-4o-mini" is not in the registry

    response = e2e_client.post(CHAT, json=_body(model="openai/gpt-4o"), headers={**tenant.headers, "x-openproxy-fallback-model": "openai/gpt-4o-mini"})

    assert response.status_code != 200
    assert "gpt-4o-mini" not in [c["body"]["model"] for c in upstream_calls(upstream)]  # never called: it is outside the authorized set
    [row] = logged_rows(tenant.org_id)
    assert row["request_metadata"]["routing"]["fallback_model_refused"] == "not_in_registry"


# ── streaming ────────────────────────────────────────────────────────────────


def test_streaming_uses_the_registry_key_and_a_refusal_is_a_plain_446(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    add_key(tenant.org_id, "sk-public-heavy", weight=100, max_class="public")
    registered = add_key(tenant.org_id, "sk-registered", max_class="internal")
    add_model(tenant.org_id, "openai/gpt-4o-mini", registered, max_class="internal")

    with e2e_client.stream("POST", CHAT, json=_body("stream me", stream=True), headers=tenant.headers) as response:
        assert response.status_code == 200
        list(response.iter_lines())
    assert {c["authorization"] for c in upstream_calls(upstream)} == {"Bearer sk-registered"}

    refused = e2e_client.post(CHAT, json=_body(SSN_TEXT, stream=True), headers=tenant.headers)
    assert refused.status_code == 446 and refused.json()["error"] == "routing_blocked"
    assert len(upstream_calls(upstream)) == 1


# ── embeddings (S4c) ─────────────────────────────────────────────────────────

EMBED = "/v1/embeddings"
EMBED_MODEL = "openai/text-embedding-3-small"


def _embed(content: str = "hello", model: str = EMBED_MODEL):
    return {"model": model, "input": content}


def test_embeddings_are_served_only_by_the_models_registry_key(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    add_key(tenant.org_id, "sk-public-heavy", weight=100, max_class="public")
    registered = add_key(tenant.org_id, "sk-registered", max_class="internal")
    add_model(tenant.org_id, EMBED_MODEL, registered, max_class="internal")

    for i in range(6):
        response = e2e_client.post(EMBED, json=_embed(f"text {i}"), headers=tenant.headers)
        assert response.status_code == 200, response.text
        assert response.headers[ROUTE_MODEL] == EMBED_MODEL and response.headers[ROUTE_REASON] == "authorized"

    assert {call["authorization"] for call in upstream_calls(upstream)} == {"Bearer sk-registered"}
    assert "route" in [stage["name"] for stage in logged_rows(tenant.org_id, 6)[0]["request_metadata"]["stages"]]


def test_an_embedding_request_too_sensitive_for_the_model_is_refused_before_any_upstream_call(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, "enforce")
    key = add_key(tenant.org_id, "sk-registered", max_class="internal")
    add_model(tenant.org_id, EMBED_MODEL, key, max_class="internal")

    response = e2e_client.post(EMBED, json=_embed(SSN_TEXT), headers=tenant.headers)

    assert response.status_code == 446
    assert response.json()["error"] == "routing_blocked" and response.json()["route_reason"] == "not_authorized:class_too_low"
    assert upstream_calls(upstream) == []
    [row] = logged_rows(tenant.org_id)
    assert row["status_code"] == 446 and row["request_metadata"]["routing"]["mode"] == "enforce"


def test_an_unregistered_embedding_model_is_refused_when_enforcing_and_only_logged_otherwise(e2e_client, upstream, make_tenant):
    enforcing = _tenant(make_tenant, "enforce")
    add_key(enforcing.org_id, "sk-any")
    assert e2e_client.post(EMBED, json=_embed(), headers=enforcing.headers).status_code == 446
    assert upstream_calls(upstream) == []

    previewing = _tenant(make_tenant, "log_only")
    add_key(previewing.org_id, "sk-any")
    response = e2e_client.post(EMBED, json=_embed(), headers=previewing.headers)
    assert response.status_code == 200 and response.headers[ROUTE_REASON] == "not_in_registry"
    assert len(upstream_calls(upstream)) == 1
