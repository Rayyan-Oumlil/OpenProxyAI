"""Prometheus metric definitions and recording helpers."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# -- Metric definitions -------------------------------------------------------

_LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, float("inf"))

requests_total = Counter(
    "openproxy_requests_total",
    "Total proxy requests",
    ["model", "provider", "status", "org_id"],
)

request_latency = Histogram(
    "openproxy_request_latency_seconds",
    "End-to-end request latency",
    ["model", "provider"],
    buckets=_LATENCY_BUCKETS,
)

ttft_seconds = Histogram(
    "openproxy_ttft_seconds",
    "Time to first token (streaming only)",
    ["model", "provider"],
    buckets=_LATENCY_BUCKETS,
)

tokens_total = Counter(
    "openproxy_tokens_total",
    "Total tokens processed",
    ["model", "provider", "token_type"],
)

cost_usd_total = Counter(
    "openproxy_cost_usd_total",
    "Total cost in USD",
    ["model", "provider"],
)

policy_violations_total = Counter(
    "openproxy_policy_violations_total",
    "Total policy violation events",
    ["reason_code", "org_id"],
)

rate_limit_hits_total = Counter(
    "openproxy_rate_limit_hits_total",
    "Total rate limit / budget exceeded events",
    ["limit_type", "org_id"],
)


# -- Recording helper ---------------------------------------------------------

def record_request(
    *,
    model: str,
    provider: str,
    status_code: int,
    org_id: str,
    latency_ms: int | None = None,
    ttft_ms: int | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
    policy_action: str | None = None,
    policy_reason_code: str | None = None,
    limit_type: str | None = None,
) -> None:
    """Record per-request metrics. Thread-safe -- prometheus_client uses locks internally."""
    status = str(status_code)

    requests_total.labels(model=model, provider=provider, status=status, org_id=org_id).inc()

    if latency_ms is not None:
        request_latency.labels(model=model, provider=provider).observe(latency_ms / 1000.0)

    if ttft_ms is not None:
        ttft_seconds.labels(model=model, provider=provider).observe(ttft_ms / 1000.0)

    if prompt_tokens:
        tokens_total.labels(model=model, provider=provider, token_type="prompt").inc(prompt_tokens)

    if completion_tokens:
        tokens_total.labels(model=model, provider=provider, token_type="completion").inc(
            completion_tokens
        )

    if cost_usd:
        cost_usd_total.labels(model=model, provider=provider).inc(cost_usd)

    if policy_action == "block" and policy_reason_code:
        policy_violations_total.labels(reason_code=policy_reason_code, org_id=org_id).inc()

    if limit_type and status_code == 429:
        rate_limit_hits_total.labels(limit_type=limit_type, org_id=org_id).inc()
