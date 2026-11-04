"""Every chat request records real per-stage timings in request_metadata["stages"] (P1-13).

The request trace page draws its waterfall from these; nothing is invented client-side.
"""

import time
import uuid
from typing import Any

import pytest
from sqlalchemy import text

from app.config import settings
from tests.e2e.conftest import _run, upstream_calls

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"


def _body(content: str, **extra: Any) -> dict:
    return {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": content}], **extra}


def _stages(org_id: uuid.UUID, count: int = 1, timeout: float = 5.0) -> list[list[dict]]:
    """Stage lists of the org's log rows, oldest first (logs are written in the background)."""

    async def query(session) -> list[list[dict]]:
        rows = await session.execute(
            text("SELECT request_metadata FROM request_logs WHERE org_id = :o ORDER BY created_at"), {"o": org_id}
        )
        return [(row[0] or {}).get("stages", []) for row in rows]

    deadline = time.time() + timeout
    while True:
        found = _run(query)
        if len(found) >= count or time.time() > deadline:
            return found
        time.sleep(0.1)


def _names(stages: list[dict]) -> list[str]:
    return [s["name"] for s in stages]


def test_a_cache_miss_records_policy_rate_limit_cache_and_upstream(e2e_client, upstream, make_tenant, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_ENABLED", True)
    tenant = make_tenant()

    assert e2e_client.post(CHAT, json=_body("trace me"), headers=tenant.headers).status_code == 200

    (stages,) = _stages(tenant.org_id)
    assert _names(stages) == ["auth", "policy", "rate_limit", "cache", "upstream"]
    for stage in stages:
        assert isinstance(stage["start_ms"], int) and isinstance(stage["ms"], int)
        assert stage["start_ms"] >= 0 and stage["ms"] >= 0
    starts = [s["start_ms"] for s in stages]
    assert starts == sorted(starts)  # stages run in order, so offsets never go backwards
    assert stages[0]["start_ms"] == 0  # the request clock starts with authentication


def test_a_cache_hit_has_no_upstream_stage(e2e_client, upstream, make_tenant, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_ENABLED", True)
    tenant = make_tenant()
    body = _body("same again")
    e2e_client.post(CHAT, json=body, headers=tenant.headers)
    e2e_client.post(CHAT, json=body, headers=tenant.headers)

    miss, hit = _stages(tenant.org_id, count=2)
    assert "upstream" in _names(miss)
    assert _names(hit) == ["auth", "policy", "rate_limit", "cache"]
    assert len(upstream_calls(upstream)) == 1


def test_a_policy_block_stops_after_the_policy_stage(e2e_client, upstream, make_tenant):
    policy = {"enforcement_mode": "enforce", "blocked_keywords": ["forbidden-word"], "pii_detection_enabled": False}
    tenant = make_tenant(org_settings={"policy": policy})

    assert e2e_client.post(CHAT, json=_body("a forbidden-word here"), headers=tenant.headers).status_code == 403

    (stages,) = _stages(tenant.org_id)
    assert _names(stages) == ["auth", "policy"]
    assert upstream_calls(upstream) == []


def test_a_streaming_request_records_the_upstream_stage(e2e_client, upstream, make_tenant):
    tenant = make_tenant()
    with e2e_client.stream("POST", CHAT, json=_body("stream it", stream=True), headers=tenant.headers) as response:
        lines = [line for line in response.iter_lines() if line.startswith("data: ")]
    assert response.status_code == 200
    assert lines[-1] == "data: [DONE]"

    (stages,) = _stages(tenant.org_id)
    assert _names(stages) == ["auth", "policy", "rate_limit", "upstream"]


def test_an_embeddings_request_is_timed_too(e2e_client, upstream, make_tenant):
    tenant = make_tenant()
    response = e2e_client.post("/v1/embeddings", json={"model": "openai/text-embedding-3-small", "input": "hello"}, headers=tenant.headers)
    assert response.status_code == 200

    (stages,) = _stages(tenant.org_id)
    assert _names(stages) == ["auth", "policy", "rate_limit", "upstream"]
    assert [s["start_ms"] for s in stages] == sorted(s["start_ms"] for s in stages)
