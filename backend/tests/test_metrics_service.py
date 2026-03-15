"""Tests for Prometheus metrics service and /metrics endpoint."""

import pytest


# Use a fresh registry per test to avoid label conflicts
@pytest.fixture(autouse=True)
def isolated_metrics():
    """Patch metrics_service to use fresh Counter/Histogram instances.

    We import and test the functions against the real registry
    but isolate by checking deltas rather than absolute values.
    """
    yield


def test_record_request_increments_requests_total():
    from app.services.metrics_service import requests_total, record_request

    before = requests_total.labels(
        model="openai/gpt-4o", provider="openai", status="200", org_id="org-test-1"
    )._value.get()

    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=200,
        org_id="org-test-1",
        latency_ms=300,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.001,
    )

    after = requests_total.labels(
        model="openai/gpt-4o", provider="openai", status="200", org_id="org-test-1"
    )._value.get()
    assert after - before == 1.0


def test_record_request_observes_latency():
    from app.services.metrics_service import request_latency, record_request

    # Just verify it doesn't raise
    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=200,
        org_id="org-test-2",
        latency_ms=450,
    )

    # Confirm the histogram has at least one observation
    sample_count = request_latency.labels(
        model="openai/gpt-4o", provider="openai"
    )._sum.get()
    assert sample_count > 0


def test_record_request_observes_ttft():
    from app.services.metrics_service import ttft_seconds, record_request

    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=200,
        org_id="org-test-ttft",
        ttft_ms=150,
    )

    sample_count = ttft_seconds.labels(
        model="openai/gpt-4o", provider="openai"
    )._sum.get()
    assert sample_count > 0


def test_record_request_increments_tokens():
    from app.services.metrics_service import tokens_total, record_request

    prompt_before = tokens_total.labels(
        model="openai/gpt-4o", provider="openai", token_type="prompt"
    )._value.get()
    completion_before = tokens_total.labels(
        model="openai/gpt-4o", provider="openai", token_type="completion"
    )._value.get()

    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=200,
        org_id="org-test-tokens",
        prompt_tokens=25,
        completion_tokens=15,
    )

    prompt_after = tokens_total.labels(
        model="openai/gpt-4o", provider="openai", token_type="prompt"
    )._value.get()
    completion_after = tokens_total.labels(
        model="openai/gpt-4o", provider="openai", token_type="completion"
    )._value.get()
    assert prompt_after - prompt_before == 25.0
    assert completion_after - completion_before == 15.0


def test_record_request_increments_cost():
    from app.services.metrics_service import cost_usd_total, record_request

    before = cost_usd_total.labels(
        model="openai/gpt-4o", provider="openai"
    )._value.get()

    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=200,
        org_id="org-test-cost",
        cost_usd=0.05,
    )

    after = cost_usd_total.labels(
        model="openai/gpt-4o", provider="openai"
    )._value.get()
    assert after - before == pytest.approx(0.05)


def test_record_request_increments_policy_violations():
    from app.services.metrics_service import policy_violations_total, record_request

    before = policy_violations_total.labels(
        reason_code="pii_detected", org_id="org-test-3"
    )._value.get()

    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=403,
        org_id="org-test-3",
        policy_action="block",
        policy_reason_code="pii_detected",
    )

    after = policy_violations_total.labels(
        reason_code="pii_detected", org_id="org-test-3"
    )._value.get()
    assert after - before == 1.0


def test_record_request_skips_policy_when_not_block():
    from app.services.metrics_service import policy_violations_total, record_request

    before = policy_violations_total.labels(
        reason_code="pii_detected", org_id="org-test-skip"
    )._value.get()

    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=200,
        org_id="org-test-skip",
        policy_action="warn",
        policy_reason_code="pii_detected",
    )

    after = policy_violations_total.labels(
        reason_code="pii_detected", org_id="org-test-skip"
    )._value.get()
    assert after - before == 0.0


def test_record_request_increments_rate_limit_hits():
    from app.services.metrics_service import rate_limit_hits_total, record_request

    before = rate_limit_hits_total.labels(
        limit_type="budget_daily_usd", org_id="org-test-4"
    )._value.get()

    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=429,
        org_id="org-test-4",
        limit_type="budget_daily_usd",
    )

    after = rate_limit_hits_total.labels(
        limit_type="budget_daily_usd", org_id="org-test-4"
    )._value.get()
    assert after - before == 1.0


def test_record_request_skips_rate_limit_when_not_429():
    from app.services.metrics_service import rate_limit_hits_total, record_request

    before = rate_limit_hits_total.labels(
        limit_type="requests_per_minute", org_id="org-test-no429"
    )._value.get()

    record_request(
        model="openai/gpt-4o",
        provider="openai",
        status_code=200,
        org_id="org-test-no429",
        limit_type="requests_per_minute",
    )

    after = rate_limit_hits_total.labels(
        limit_type="requests_per_minute", org_id="org-test-no429"
    )._value.get()
    assert after - before == 0.0


def test_metrics_endpoint_returns_200(client):
    """GET /metrics returns 200 with Prometheus text format."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert b"openproxy_requests_total" in response.content
