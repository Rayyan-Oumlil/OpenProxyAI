"""Data classification through the real pipeline (Phase 2, S3): header, detection, org default, logging, blocks."""

import time
from typing import Any

import pytest
from sqlalchemy import text

from tests.e2e.conftest import _run, upstream_calls

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"
EMBED = "/v1/embeddings"
CLASS_HEADER = "x-openproxyai-data-class"
SSN_TEXT = "My SSN is 123-45-6789, please draft the letter."


def _body(content: str = "hello"):
    return {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": content}]}


def _logged_metadata(org_id, count: int = 1, timeout: float = 5.0) -> list[dict[str, Any]]:
    async def query(session) -> list[dict[str, Any]]:
        result = await session.execute(
            text("SELECT request_metadata FROM request_logs WHERE org_id = :o ORDER BY created_at"), {"o": org_id}
        )
        return [row[0] or {} for row in result]

    deadline = time.time() + timeout
    while True:
        rows = _run(query)
        if len(rows) >= count or time.time() > deadline:
            return rows
        time.sleep(0.1)


def _tenant(make_tenant, **policy):
    return make_tenant(org_settings={"policy": {"enforcement_mode": "log_only", **policy}})


def test_a_plain_request_gets_the_org_default_class(e2e_client, make_tenant):
    tenant = make_tenant()
    response = e2e_client.post(CHAT, json=_body(), headers=tenant.headers)
    assert response.status_code == 200
    assert response.headers[CLASS_HEADER] == "internal"
    [meta] = _logged_metadata(tenant.org_id)
    assert meta["data_class"] == {"class": "internal", "source": "default", "entities": []}
    assert "classify" in [stage["name"] for stage in meta["stages"]]


def test_detected_pii_raises_the_class_without_blocking_in_log_only_mode(e2e_client, upstream, make_tenant):
    tenant = _tenant(make_tenant)
    response = e2e_client.post(CHAT, json=_body(SSN_TEXT), headers=tenant.headers)
    assert response.status_code == 200 and len(upstream_calls(upstream)) == 1
    assert response.headers[CLASS_HEADER] == "confidential"
    [meta] = _logged_metadata(tenant.org_id)
    assert meta["data_class"] == {"class": "confidential", "source": "detected", "entities": ["ssn"]}
    assert "123-45-6789" not in str(meta)  # names of the kinds only, never the text


def test_the_callers_header_can_raise_the_class_but_not_lower_it(e2e_client, make_tenant):
    tenant = make_tenant()
    raised = e2e_client.post(CHAT, json=_body(), headers={**tenant.headers, "x-openproxy-data-class": "secret"})
    assert raised.headers[CLASS_HEADER] == "secret"

    lowered = e2e_client.post(CHAT, json=_body(SSN_TEXT), headers={**tenant.headers, "x-openproxy-data-class": "public"})
    assert lowered.headers[CLASS_HEADER] == "confidential"  # the header was ignored where it would lower the class


def test_an_unknown_class_in_the_header_is_rejected_before_anything_is_sent(e2e_client, upstream, make_tenant):
    tenant = make_tenant()
    response = e2e_client.post(CHAT, json=_body(), headers={**tenant.headers, "x-openproxy-data-class": "top-secret"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_data_class"
    assert upstream_calls(upstream) == []


def test_org_default_and_map_overrides_apply(e2e_client, make_tenant):
    tenant = _tenant(make_tenant, default_data_class="public", data_class_map={"email": "secret"})
    plain = e2e_client.post(CHAT, json=_body(), headers=tenant.headers)
    assert plain.headers[CLASS_HEADER] == "public"
    with_email = e2e_client.post(CHAT, json=_body("write to jane@example.com"), headers=tenant.headers)
    assert with_email.headers[CLASS_HEADER] == "secret"


def test_a_blocked_request_is_still_classified_in_the_audit_row(e2e_client, upstream, make_tenant):
    tenant = make_tenant(org_settings={"policy": {"enforcement_mode": "enforce"}})
    response = e2e_client.post(CHAT, json=_body(SSN_TEXT), headers=tenant.headers)
    assert response.status_code == 446 and upstream_calls(upstream) == []
    [meta] = _logged_metadata(tenant.org_id)
    assert meta["data_class"]["class"] == "confidential"


def test_embeddings_are_classified_too(e2e_client, make_tenant):
    tenant = _tenant(make_tenant)
    response = e2e_client.post(EMBED, json={"model": "openai/text-embedding-3-small", "input": SSN_TEXT}, headers=tenant.headers)
    assert response.status_code == 200
    assert response.headers[CLASS_HEADER] == "confidential"
    [meta] = _logged_metadata(tenant.org_id)
    assert meta["data_class"]["entities"] == ["ssn"]


def test_pii_detection_off_means_no_scanning_for_classification(e2e_client, make_tenant):
    tenant = _tenant(make_tenant, pii_detection_enabled=False)
    response = e2e_client.post(CHAT, json=_body(SSN_TEXT), headers=tenant.headers)
    assert response.headers[CLASS_HEADER] == "internal"
