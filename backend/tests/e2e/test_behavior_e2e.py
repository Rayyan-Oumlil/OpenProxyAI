"""Behaviour settings through the real chat pipeline: what the provider actually receives, and what the caller is told."""

import time

import pytest

from app.config import settings
from app.services import behavior as bh
from sqlalchemy import text

from tests.e2e.conftest import _run, admin_headers, upstream_calls

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"
HEADER = "x-openproxy-behavior"
MODEL = "openai/gpt-4o-mini"


def _body(content: str = "hello", **extra):
    model = extra.pop("model", MODEL)
    return {"model": model, "messages": [{"role": "user", "content": content}], **extra}


def _tenant(make_tenant, **policy):
    return make_tenant(org_settings={"policy": policy} if policy else None)


def _sent(upstream):
    [call] = upstream_calls(upstream)
    return call["body"]


def _log(org_id, timeout=5.0):
    async def query(session):
        result = await session.execute(text("SELECT status_code, request_metadata FROM request_logs WHERE org_id = :o ORDER BY created_at"), {"o": org_id})
        return [dict(row._mapping) for row in result]

    deadline = time.time() + timeout
    while True:
        rows = _run(query)
        if rows or time.time() > deadline:
            return rows[0]
        time.sleep(0.1)


# ── nothing asked, nothing configured: today's behaviour ────────────────────

def test_without_behaviour_the_callers_parameters_reach_the_provider_unchanged(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    response = e2e_client.post(CHAT, json=_body(temperature=1.7, max_tokens=9999, top_p=0.4), headers=tenant.headers)
    assert response.status_code == 200
    sent = _sent(upstream)
    assert (sent["temperature"], sent["max_tokens"], sent["top_p"]) == (1.7, 9999, 0.4)
    assert "reasoning_effort" not in sent and "behavior" not in sent
    assert "x-openproxyai-behavior" not in response.headers
    assert "behavior" not in (_log(tenant.org_id)["request_metadata"] or {})


# ── a caller asks ───────────────────────────────────────────────────────────

def test_a_header_setting_becomes_provider_parameters_and_is_reported(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    response = e2e_client.post(CHAT, json=_body(), headers={**tenant.headers, HEADER: "creativity=low; max_response_length=short"})
    assert response.status_code == 200
    sent = _sent(upstream)
    assert sent["temperature"] == bh.TEMPERATURE["low"] and sent["max_tokens"] == bh.MAX_TOKENS["short"]
    assert response.headers["x-openproxyai-behavior"] == "creativity=low; max_response_length=short"
    recorded = _log(tenant.org_id)["request_metadata"]["behavior"]
    assert recorded["effective"] == {"creativity": "low", "max_response_length": "short"}
    assert recorded["applied"] == {"temperature": bh.TEMPERATURE["low"], "max_tokens": bh.MAX_TOKENS["short"]}


def test_a_body_setting_wins_over_the_header_and_is_never_forwarded(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    e2e_client.post(CHAT, json=_body(behavior={"creativity": "high"}), headers={**tenant.headers, HEADER: "creativity=low"})
    sent = _sent(upstream)
    assert sent["temperature"] == bh.TEMPERATURE["high"]
    assert "behavior" not in sent


@pytest.mark.parametrize("header", ["creativity=wild", "tone=low", "creativity"])
def test_an_invalid_setting_is_a_400_and_nothing_is_sent(e2e_client, upstream, make_tenant, header):
    tenant = _tenant(make_tenant)
    response = e2e_client.post(CHAT, json=_body(), headers={**tenant.headers, HEADER: header})
    assert response.status_code == 400 and response.json()["error"] == "invalid_behavior"
    assert upstream_calls(upstream) == []


def test_an_invalid_body_setting_is_a_400(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    response = e2e_client.post(CHAT, json=_body(behavior={"creativity": "wild"}), headers=tenant.headers)
    assert response.status_code == 400 and upstream_calls(upstream) == []


def test_a_setting_the_model_cannot_honour_is_ignored_and_recorded_not_sent(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    e2e_client.post(CHAT, json=_body(), headers={**tenant.headers, HEADER: "reasoning_depth=high"})  # gpt-4o-mini takes no reasoning_effort
    assert "reasoning_effort" not in _sent(upstream)
    recorded = _log(tenant.org_id)["request_metadata"]["behavior"]
    assert [i["param"] for i in recorded["ignored"]] == ["reasoning_effort"] and recorded["applied"] == {}


def test_a_reasoning_model_gets_the_reasoning_effort(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    e2e_client.post(CHAT, json=_body(model="openai/o3-mini"), headers={**tenant.headers, HEADER: "reasoning_depth=high"})
    assert _sent(upstream)["reasoning_effort"] == "high"


def test_citations_add_an_instruction_after_the_system_messages(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    messages = [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}]
    e2e_client.post(CHAT, json={"model": MODEL, "messages": messages}, headers={**tenant.headers, HEADER: "citations=true"})
    sent = _sent(upstream)["messages"]
    assert [m["role"] for m in sent] == ["system", "system", "user"] and sent[1]["content"] == bh.CITATION_INSTRUCTION


# ── the org decides ─────────────────────────────────────────────────────────

def test_the_ceiling_lowers_a_request_and_says_so(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, behavior_ceiling={"creativity": "low"})
    response = e2e_client.post(CHAT, json=_body(), headers={**tenant.headers, HEADER: "creativity=high"})
    assert _sent(upstream)["temperature"] == bh.TEMPERATURE["low"]
    assert response.headers["x-openproxyai-behavior"] == "creativity=low"
    assert response.headers["x-openproxyai-behavior-clamped"] == "creativity"
    assert _log(tenant.org_id)["request_metadata"]["behavior"]["clamped"] == ["creativity"]


def test_the_ceiling_also_lowers_the_callers_own_parameters(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, behavior_ceiling={"creativity": "low", "max_response_length": "short"})
    e2e_client.post(CHAT, json=_body(temperature=2, max_tokens=30000), headers=tenant.headers)
    sent = _sent(upstream)
    assert (sent["temperature"], sent["max_tokens"]) == (bh.TEMPERATURE["low"], bh.MAX_TOKENS["short"])
    assert len(_log(tenant.org_id)["request_metadata"]["behavior"]["clamped_params"]) == 2


def test_a_value_inside_the_ceiling_is_left_alone(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, behavior_ceiling={"creativity": "medium", "max_response_length": "long"})
    e2e_client.post(CHAT, json=_body(temperature=0.1, max_tokens=50), headers=tenant.headers)
    sent = _sent(upstream)
    assert (sent["temperature"], sent["max_tokens"]) == (0.1, 50)


def test_an_org_default_applies_when_the_caller_says_nothing_and_an_explicit_parameter_beats_it(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant, behavior_defaults={"max_response_length": "short"})
    e2e_client.post(CHAT, json=_body("one"), headers=tenant.headers)
    assert _sent(upstream)["max_tokens"] == bh.MAX_TOKENS["short"]
    e2e_client.post(CHAT, json=_body("two", max_tokens=77), headers=tenant.headers)
    assert upstream_calls(upstream)[-1]["body"]["max_tokens"] == 77


# ── the cache must not hand one setting's answer to another ─────────────────

def test_different_creativity_is_not_served_from_the_same_cache_entry(e2e_client, upstream, make_tenant, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_ENABLED", True)
    tenant = _tenant(make_tenant)
    for level in ("low", "high", "low"):
        e2e_client.post(CHAT, json=_body("cache probe"), headers={**tenant.headers, HEADER: f"creativity={level}"})
    assert len(upstream_calls(upstream)) == 2  # low, high; the second low is a cache hit


def test_a_setting_the_cache_key_does_not_cover_skips_the_cache(e2e_client, upstream, make_tenant, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_ENABLED", True)
    tenant = _tenant(make_tenant)
    for _ in range(2):
        e2e_client.post(CHAT, json=_body("length probe"), headers={**tenant.headers, HEADER: "max_response_length=short"})
    assert len(upstream_calls(upstream)) == 2


# ── the admin API ───────────────────────────────────────────────────────────

POLICY = "/api/v1/organizations/current/policy"


def test_an_admin_sets_a_ceiling_through_the_api_and_the_next_request_obeys_it(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    admin = admin_headers(e2e_client, tenant)
    saved = e2e_client.patch(POLICY, json={"behavior_ceiling": {"creativity": "low"}, "behavior_defaults": {"citations": True}}, headers=admin)
    assert saved.status_code == 200, saved.text
    assert saved.json()["behavior_ceiling"] == {"creativity": "low"} and saved.json()["behavior_defaults"] == {"citations": True}
    assert e2e_client.get(POLICY, headers=admin).json()["behavior_ceiling"] == {"creativity": "low"}

    response = e2e_client.post(CHAT, json=_body(), headers={**tenant.headers, HEADER: "creativity=high"})
    sent = _sent(upstream)
    assert sent["temperature"] == bh.TEMPERATURE["low"] and response.headers["x-openproxyai-behavior-clamped"] == "creativity"
    assert sent["messages"][0] == {"role": "system", "content": bh.CITATION_INSTRUCTION}  # the default asked for citations


def test_clearing_and_replacing_behaviour_settings_through_the_api(e2e_client, make_tenant):
    tenant = _tenant(make_tenant, behavior_ceiling={"creativity": "low", "max_response_length": "short"})
    admin = admin_headers(e2e_client, tenant)
    replaced = e2e_client.patch(POLICY, json={"behavior_ceiling": {"max_response_length": "long"}}, headers=admin).json()
    assert replaced["behavior_ceiling"] == {"max_response_length": "long"}  # the whole object is replaced, as documented
    assert e2e_client.patch(POLICY, json={"behavior_ceiling": {"creativity": None}}, headers=admin).json()["behavior_ceiling"] == {}


@pytest.mark.parametrize("body", [
    {"behavior_ceiling": None}, {"behavior_defaults": None}, {"behavior_ceiling": {"creativity": "wild"}},
    {"behavior_ceiling": {"citations": True}}, {"behavior_defaults": {"tone": "formal"}},
])
def test_the_api_refuses_what_it_cannot_store_safely(e2e_client, make_tenant, body):
    tenant = _tenant(make_tenant, behavior_ceiling={"creativity": "low"})
    admin = admin_headers(e2e_client, tenant)
    assert e2e_client.patch(POLICY, json=body, headers=admin).status_code == 422
    assert e2e_client.get(POLICY, headers=admin).json()["behavior_ceiling"] == {"creativity": "low"}  # a refused save changes nothing


# ── aliases cannot walk around a ceiling ────────────────────────────────────

@pytest.mark.parametrize("alias", ["max_completion_tokens", "max_output_tokens"])
def test_a_length_alias_is_clamped_to_the_ceiling_at_the_provider(e2e_client, upstream, make_tenant, alias):
    tenant = _tenant(make_tenant, behavior_ceiling={"max_response_length": "short"})
    e2e_client.post(CHAT, json=_body(**{alias: 30000}), headers=tenant.headers)
    assert _sent(upstream)[alias] == bh.MAX_TOKENS["short"]


@pytest.mark.parametrize("extra", [
    {"top_p": 0.99}, {"top_k": 500}, {"reasoning": {"effort": "high"}}, {"thinking": {"budget_tokens": 100000}},
    {"extra_body": {"max_tokens": 99999}}, {"generation_config": {"maxOutputTokens": 99999}},
])
def test_unmapped_generation_parameters_never_reach_the_provider_while_a_ceiling_is_active(e2e_client, upstream, make_tenant, extra):
    ceiling = {"creativity": "low", "reasoning_depth": "low", "max_response_length": "short"}
    tenant = _tenant(make_tenant, behavior_ceiling=ceiling)
    response = e2e_client.post(CHAT, json=_body(**extra), headers=tenant.headers)
    assert response.status_code == 200
    sent = _sent(upstream)
    assert not set(extra) & set(sent)
    assert set(extra) <= set(_log(tenant.org_id)["request_metadata"]["behavior"]["removed"])


def test_with_no_ceiling_those_parameters_are_left_exactly_as_sent(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    e2e_client.post(CHAT, json=_body(top_p=0.4, max_completion_tokens=77), headers=tenant.headers)
    sent = _sent(upstream)
    assert (sent["top_p"], sent["max_completion_tokens"]) == (0.4, 77)
