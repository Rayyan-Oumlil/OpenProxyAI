"""Telemetry through the real pipeline: events and spans appear, and exporter failure never changes the HTTP result."""

import time

import pytest

from app.services.telemetry import telemetry
from tests.e2e.conftest import fetch_request_logs, upstream_calls

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"
POLICY = {"enforcement_mode": "enforce", "blocked_keywords": ["forbidden-word"], "pii_detection_enabled": False}


class Recorder:
    def __init__(self):
        self.items = []

    def emit(self, item):
        self.items.append(item)


class Exploding:
    def emit(self, item):
        raise RuntimeError("exporter is on fire")


@pytest.fixture
def recorders(monkeypatch):
    siem, otel = Recorder(), Recorder()
    monkeypatch.setattr(telemetry, "siem", siem)
    monkeypatch.setattr(telemetry, "otel", otel)
    return siem, otel


@pytest.fixture
def exploding(monkeypatch):
    monkeypatch.setattr(telemetry, "siem", Exploding())
    monkeypatch.setattr(telemetry, "otel", Exploding())


def _body(content):
    return {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": content}]}


def _wait(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while not predicate() and time.time() < deadline:
        time.sleep(0.05)
    return predicate()


def test_a_successful_request_produces_a_gen_ai_span_and_no_security_event(e2e_client, upstream, make_tenant, recorders):
    siem, otel = recorders
    tenant = make_tenant()
    assert e2e_client.post(CHAT, json=_body("hello"), headers=tenant.headers).status_code == 200
    assert _wait(lambda: otel.items)
    [span] = otel.items
    assert span.name == "chat openai/gpt-4o-mini" and span.error is None
    assert span.attributes["gen_ai.usage.input_tokens"] == 10 and span.attributes["gen_ai.usage.output_tokens"] == 5
    assert str(tenant.org_id) == span.attributes["openproxyai.org_id"]
    assert siem.items == []


def test_a_policy_block_produces_a_siem_event_without_the_prompt(e2e_client, upstream, make_tenant, recorders):
    siem, otel = recorders
    tenant = make_tenant(org_settings={"policy": POLICY})
    assert e2e_client.post(CHAT, json=_body("this has a forbidden-word inside"), headers=tenant.headers).status_code == 446
    assert _wait(lambda: siem.items)
    [event] = siem.items
    assert event.name == "AI-DLP-BLOCK" and event.reason == "blocked_keyword" and str(event.org_id) == str(tenant.org_id)
    assert "forbidden-word" not in repr(event) and "forbidden-word" not in repr(otel.items)
    assert otel.items[0].error == "policy_blocked"


def test_exporter_failure_never_changes_a_successful_response(e2e_client, upstream, make_tenant, exploding):
    tenant = make_tenant()
    response = e2e_client.post(CHAT, json=_body("ping"), headers=tenant.headers)
    assert response.status_code == 200 and response.json()["choices"][0]["message"]["content"] == "echo: ping"
    [call] = upstream_calls(upstream)
    assert call["body"]["model"] == "gpt-4o-mini"
    assert _wait(lambda: fetch_request_logs(tenant.org_id))  # the audit row is still written
    assert fetch_request_logs(tenant.org_id)[0]["status_code"] == 200


def test_exporter_failure_never_changes_a_policy_block(e2e_client, upstream, make_tenant, exploding):
    tenant = make_tenant(org_settings={"policy": POLICY})
    response = e2e_client.post(CHAT, json=_body("forbidden-word"), headers=tenant.headers)
    assert response.status_code == 446 and upstream_calls(upstream) == []
    assert _wait(lambda: fetch_request_logs(tenant.org_id))
    assert fetch_request_logs(tenant.org_id)[0]["error_message"].startswith("policy_blocked")


def test_exporter_failure_never_changes_a_streaming_response(e2e_client, upstream, make_tenant, exploding):
    tenant = make_tenant()
    with e2e_client.stream("POST", CHAT, json={**_body("stream me"), "stream": True}, headers=tenant.headers) as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line.startswith("data: ")]
    assert lines[-1] == "data: [DONE]"
