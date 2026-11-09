"""The policy preview must never disagree with the real pipeline, and must never have side effects (Phase 2, S5)."""

import pytest

from tests.e2e.conftest import admin_headers, upstream_calls
from tests.e2e.test_routing_e2e import CHAT, SSN_TEXT, _body, add_key, add_model, logged_rows

PREVIEW = "/api/v1/policy/preview"


def _tenant(make_tenant, mode="enforce", **policy):
    return make_tenant(provider_keys=(), org_settings={"policy": {"enforcement_mode": "log_only", "routing_mode": mode, **policy}})


def _preview(client, tenant, content="hello", model="openai/gpt-4o-mini", data_class=None, **extra):
    body = {"model": model, "messages": [{"role": "user", "content": content}], **({"data_class": data_class} if data_class else {}), **extra}
    return client.post(PREVIEW, json=body, headers=admin_headers(client, tenant))


@pytest.fixture
def registered(make_tenant):
    """An org enforcing routing: gpt-4o-mini cleared for internal, gpt-4o for confidential (both vision-capable)."""
    tenant = _tenant(make_tenant)
    small = add_key(tenant.org_id, "sk-small", max_class="internal")
    big = add_key(tenant.org_id, "sk-big", max_class="confidential")
    add_model(tenant.org_id, "openai/gpt-4o-mini", small, max_class="internal", capabilities=["VISION"], cost_tier="low")
    add_model(tenant.org_id, "openai/gpt-4o", big, max_class="confidential", capabilities=["VISION"], cost_tier="high")
    return tenant


# (label, request content, model, data class asserted by the caller)
SCENARIOS = [
    ("authorized", "plain question", "openai/gpt-4o-mini", None),
    ("cleared model for sensitive data", "plain question", "openai/gpt-4o", "confidential"),
    ("too sensitive for the model (header)", "plain question", "openai/gpt-4o-mini", "confidential"),
    ("too sensitive for the model (detected SSN)", SSN_TEXT, "openai/gpt-4o-mini", None),
    ("nothing cleared for secret", "plain question", "openai/gpt-4o", "secret"),
    ("model not in the registry", "plain question", "openai/gpt-4.1-mini", None),
    ("capability, internal data", "plain question", "cap:VISION", None),
    ("capability, confidential data", "plain question", "cap:VISION", "confidential"),
    ("capability nobody has", "plain question", "cap:AUDIO", None),
]


@pytest.mark.parametrize("label,content,model,data_class", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_the_preview_predicts_exactly_what_the_real_request_does(e2e_client, upstream, registered, label, content, model, data_class):
    preview = _preview(e2e_client, registered, content, model, data_class).json()
    headers = {**registered.headers, **({"x-openproxy-data-class": data_class} if data_class else {})}
    actual = e2e_client.post(CHAT, json=_body(content, model=model), headers=headers)

    assert preview["data_class"]["class"] == actual.headers.get("x-openproxyai-data-class", preview["data_class"]["class"])
    if preview["verdict"] == "allowed":
        assert actual.status_code == 200, actual.text
        assert preview["routing"]["model"] == actual.headers["x-openproxyai-route-model"]
        assert preview["routing"]["reason"] == actual.headers["x-openproxyai-route-reason"]
    else:
        assert preview["verdict"] == "blocked_by_routing"
        assert actual.status_code == 446 and actual.json()["error"] == "routing_blocked"
        assert preview["routing"]["reason"] == actual.json()["route_reason"]
        assert preview["routing"]["model"] is None


def test_the_preview_names_the_key_and_why_each_other_model_was_ruled_out(e2e_client, registered):
    preview = _preview(e2e_client, registered, SSN_TEXT, "openai/gpt-4o").json()
    assert preview["data_class"] == {"class": "confidential", "source": "detected", "entities": ["ssn"]}
    assert preview["routing"]["model"] == "openai/gpt-4o" and preview["routing"]["authorized"] == ["openai/gpt-4o"]
    assert preview["routing"]["excluded"] == {"openai/gpt-4o-mini": "class_too_low"}
    assert preview["routing"]["key_alias"].startswith("k-")
    assert "sk-big" not in str(preview) and "123-45-6789" not in str(preview)  # never a credential, never the text


def test_it_previews_enforcement_before_it_is_turned_on(e2e_client, make_tenant):
    for mode in ("off", "log_only"):
        tenant = _tenant(make_tenant, mode)
        key = add_key(tenant.org_id, "sk-x", max_class="internal")
        add_model(tenant.org_id, "openai/gpt-4o-mini", key, max_class="internal")
        preview = _preview(e2e_client, tenant, data_class="confidential").json()
        assert preview["routing"]["current_mode"] == mode
        assert preview["verdict"] == "would_block_if_enforced" and preview["routing"]["model"] is None
        assert _preview(e2e_client, tenant).json()["verdict"] == "allowed"


def test_a_policy_block_is_reported_before_routing_is_considered(e2e_client, make_tenant):
    tenant = make_tenant(provider_keys=(), org_settings={"policy": {"enforcement_mode": "enforce", "blocked_keywords": ["forbidden-word"], "routing_mode": "enforce"}})
    preview = _preview(e2e_client, tenant, "this has a forbidden-word inside").json()
    assert preview["verdict"] == "blocked_by_policy" and preview["policy"]["allowed"] is False
    assert preview["policy"]["reason_code"] == "blocked_keyword"
    actual = e2e_client.post(CHAT, json=_body("this has a forbidden-word inside"), headers=tenant.headers)
    assert actual.status_code == 446 and actual.json()["error"] == "policy_violation"


def test_a_fallback_model_is_judged_by_the_same_rules(e2e_client, registered):
    ok = _preview(e2e_client, registered, model="openai/gpt-4o-mini", fallback_model="openai/gpt-4o").json()["fallback"]
    assert ok == {"model": "openai/gpt-4o", "authorized": True, "reason": "authorized"}
    refused = _preview(e2e_client, registered, model="openai/gpt-4o", data_class="confidential", fallback_model="openai/gpt-4o-mini").json()["fallback"]
    assert refused == {"model": "openai/gpt-4o-mini", "authorized": False, "reason": "not_authorized:class_too_low"}


def test_a_preview_has_no_side_effects(e2e_client, upstream, registered):
    """No upstream call and no audit row."""
    for i in range(5):
        assert _preview(e2e_client, registered, f"preview {i}").status_code == 200
    assert upstream_calls(upstream) == []
    assert logged_rows(registered.org_id, 0, timeout=0.3) == []


def test_a_preview_does_not_use_up_the_rate_limit(e2e_client, make_tenant, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "DEFAULT_RATE_LIMIT_RPM", 2)
    tenant = _tenant(make_tenant)
    key = add_key(tenant.org_id, "sk-x")
    add_model(tenant.org_id, "openai/gpt-4o-mini", key)
    for _ in range(6):
        _preview(e2e_client, tenant)
    assert [e2e_client.post(CHAT, json=_body(f"r{i}"), headers=tenant.headers).status_code for i in range(3)] == [200, 200, 429]


def test_a_preview_needs_an_admin_session_not_a_gateway_key(e2e_client, registered):
    body = {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
    assert e2e_client.post(PREVIEW, json=body).status_code == 401
    assert e2e_client.post(PREVIEW, json=body, headers=registered.headers).status_code == 401  # a proxy key is not a console login


def test_bad_input_is_rejected_like_the_real_endpoint_would(e2e_client, registered):
    assert _preview(e2e_client, registered, data_class="top-secret").status_code == 422
    assert _preview(e2e_client, registered, model="gpt-4o").status_code == 400  # not provider/name
    assert e2e_client.post(PREVIEW, json={"model": "openai/gpt-4o", "messages": []}, headers=admin_headers(e2e_client, registered)).status_code == 422
