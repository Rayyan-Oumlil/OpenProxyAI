"""End-to-end pipeline tests: real app, no dependency overrides, fake upstream (P0-8)."""

import json
import time
from decimal import Decimal

import pytest

from app.config import settings
from tests.e2e.conftest import fetch_request_logs, upstream_calls

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"


def _body(content: str = "hello", model: str = "openai/gpt-4o-mini", **extra):
    return {"model": model, "messages": [{"role": "user", "content": content}], **extra}


def _wait_for_logs(org_id, count, timeout=5.0):
    deadline = time.time() + timeout
    while True:
        logs = fetch_request_logs(org_id)
        if len(logs) >= count or time.time() > deadline:
            return logs
        time.sleep(0.1)


def test_missing_or_invalid_key_is_401(e2e_client):
    assert e2e_client.post(CHAT, json=_body()).status_code == 401
    assert e2e_client.post(CHAT, json=_body(), headers={"Authorization": "Bearer opai_dev_nope"}).status_code == 401
    assert e2e_client.post(CHAT, json=_body(), headers={"Authorization": "Bearer not-a-gateway-key"}).status_code == 401


def test_chat_round_trip_reaches_upstream_and_writes_audit_row(e2e_client, upstream, make_tenant):
    tenant = make_tenant()
    response = e2e_client.post(CHAT, json=_body("ping"), headers=tenant.headers)

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "echo: ping"

    [call] = upstream_calls(upstream)
    assert call["authorization"] == "Bearer sk-good"
    assert call["body"]["model"] == "gpt-4o-mini"

    [log] = _wait_for_logs(tenant.org_id, 1)
    assert (log["status_code"], log["prompt_tokens"], log["completion_tokens"]) == (200, 10, 5)
    assert log["cost_usd"] > Decimal("0")


def test_identical_request_is_served_from_cache(e2e_client, upstream, make_tenant, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_ENABLED", True)
    tenant = make_tenant()
    body = _body("cache me")

    first = e2e_client.post(CHAT, json=body, headers=tenant.headers)
    second = e2e_client.post(CHAT, json=body, headers=tenant.headers)

    assert first.status_code == second.status_code == 200
    assert second.json()["choices"] == first.json()["choices"]
    assert len(upstream_calls(upstream)) == 1


def test_cache_is_not_shared_between_orgs(e2e_client, upstream, make_tenant, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_ENABLED", True)
    body = _body("same prompt, two tenants")
    org_a, org_b = make_tenant(), make_tenant()

    assert e2e_client.post(CHAT, json=body, headers=org_a.headers).status_code == 200
    assert e2e_client.post(CHAT, json=body, headers=org_b.headers).status_code == 200

    assert len(upstream_calls(upstream)) == 2


def test_rate_limit_returns_429(e2e_client, make_tenant, monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_RATE_LIMIT_RPM", 2)
    tenant = make_tenant()

    statuses = [e2e_client.post(CHAT, json=_body(f"r{i}"), headers=tenant.headers).status_code for i in range(3)]

    assert statuses == [200, 200, 429]


def test_blocked_keyword_is_blocked_and_never_reaches_upstream(e2e_client, upstream, make_tenant):
    policy = {"enforcement_mode": "enforce", "blocked_keywords": ["forbidden-word"], "pii_detection_enabled": False}
    tenant = make_tenant(org_settings={"policy": policy})

    response = e2e_client.post(CHAT, json=_body("this has a forbidden-word inside"), headers=tenant.headers)

    assert response.status_code == 403  # becomes 446 once decision D6 is made
    assert upstream_calls(upstream) == []
    [log] = _wait_for_logs(tenant.org_id, 1)
    assert log["status_code"] == 403
    assert log["error_message"].startswith("policy_blocked")


def test_over_budget_returns_402(e2e_client, upstream, make_tenant, monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_BUDGET_DAILY_USD", 0.0000001)
    tenant = make_tenant()

    response = e2e_client.post(CHAT, json=_body("budget", stream=True), headers=tenant.headers)

    assert response.status_code == 402
    assert upstream_calls(upstream) == []


def test_stream_completes_with_done_and_bills_usage(e2e_client, upstream, make_tenant):
    tenant = make_tenant()

    with e2e_client.stream("POST", CHAT, json=_body("stream me", stream=True), headers=tenant.headers) as response:
        lines = [line for line in response.iter_lines() if line.startswith("data: ")]

    assert response.status_code == 200
    assert lines[-1] == "data: [DONE]"
    text_out = "".join(
        (json.loads(line[6:])["choices"] or [{"delta": {}}])[0]["delta"].get("content") or "" for line in lines[:-1]
    )
    assert text_out == "echo: stream me"
    assert upstream_calls(upstream)[0]["body"]["stream_options"]["include_usage"] is True
    assert all('"usage"' not in line for line in lines), "usage chunk leaked to a client that did not ask for it"

    [log] = _wait_for_logs(tenant.org_id, 1)
    assert (log["status_code"], log["prompt_tokens"], log["completion_tokens"]) == (200, 10, 5)


def test_failing_key_falls_back_to_a_good_key(e2e_client, upstream, make_tenant):
    tenant = make_tenant(provider_keys=(("sk-bad", 100), ("sk-good", 1)))

    response = e2e_client.post(CHAT, json=_body("fallback"), headers=tenant.headers)

    assert response.status_code == 200
    assert upstream_calls(upstream)[-1]["authorization"] == "Bearer sk-good"


def test_tool_calling_request_reaches_upstream_unchanged(e2e_client, upstream, make_tenant):
    tenant = make_tenant()
    tool_call = {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": '{"q": "x"}'}}
    body = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "use the tool"},
            {"role": "assistant", "content": None, "tool_calls": [tool_call]},
            {"role": "tool", "tool_call_id": "call_1", "content": "result"},
        ],
        "tools": [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "response_format": {"type": "json_object"},
    }

    assert e2e_client.post(CHAT, json=body, headers=tenant.headers).status_code == 200

    sent = upstream_calls(upstream)[0]["body"]
    assert sent["messages"][1]["tool_calls"] == [tool_call]
    assert sent["messages"][2]["tool_call_id"] == "call_1"
    for field in ("tools", "tool_choice", "parallel_tool_calls", "response_format"):
        assert sent[field] == body[field]
