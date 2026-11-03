"""The dashboard overview agrees with itself right after traffic, without waiting for the 5-minute view refresh (P1-16).

Totals used to come from the materialized view mv_daily_spend (refreshed every 5 minutes) while the
success/failure counts came live from request_logs, so a fresh deployment showed "0 total, 3 successful".
"""

import time
import uuid
from typing import Any

import pytest
from sqlalchemy import text

from app.services.auth_service import create_access_token
from tests.e2e.conftest import _run, fetch_request_logs

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"


def _body(content: str) -> dict[str, Any]:
    return {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": content}]}


def _admin_headers(org_id: uuid.UUID) -> dict[str, str]:
    async def user_id(session) -> uuid.UUID:
        return (await session.execute(text("SELECT id FROM users WHERE org_id = :o"), {"o": org_id})).scalar_one()

    token = create_access_token(str(_run(user_id)), str(org_id), "admin")
    return {"Authorization": f"Bearer {token}"}


def _wait_for_logs(org_id: uuid.UUID, count: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while len(fetch_request_logs(org_id)) < count and time.time() < deadline:
        time.sleep(0.1)


def test_overview_totals_match_the_live_counts_immediately(e2e_client, upstream, make_tenant):
    tenant = make_tenant()
    for prompt in ("one", "two", "three"):
        assert e2e_client.post(CHAT, json=_body(prompt), headers=tenant.headers).status_code == 200
    _wait_for_logs(tenant.org_id, 3)

    response = e2e_client.get("/api/v1/analytics/overview?period_days=7", headers=_admin_headers(tenant.org_id))

    assert response.status_code == 200
    body = response.json()
    overview = body["overview"]
    # The panels beside the tiles read the same live data, so none of them is empty while the tiles are not.
    assert [(m["model"], m["requests"]) for m in body["by_model"]] == [("openai/gpt-4o-mini", 3)]
    assert [(u["requests"]) for u in body["by_user"]] == [3]
    assert [(d["requests"], d["tokens"]) for d in body["daily_trend"]] == [(3, 45)]
    assert overview["successful_requests"] == 3
    assert overview["total_requests"] == 3
    assert overview["total_tokens"] == 45  # 3 requests x (10 prompt + 5 completion) from the fake upstream
    assert overview["total_cost_usd"] > 0
    assert overview["projected_month_end_cost_usd"] is not None


def test_total_requests_is_always_successful_plus_failed(e2e_client, upstream, make_tenant):
    policy = {"enforcement_mode": "enforce", "blocked_keywords": ["forbidden-word"], "pii_detection_enabled": False}
    tenant = make_tenant(org_settings={"policy": policy})
    assert e2e_client.post(CHAT, json=_body("fine"), headers=tenant.headers).status_code == 200
    assert e2e_client.post(CHAT, json=_body("a forbidden-word"), headers=tenant.headers).status_code == 403
    _wait_for_logs(tenant.org_id, 2)

    overview = e2e_client.get("/api/v1/analytics/overview?period_days=7", headers=_admin_headers(tenant.org_id)).json()["overview"]

    assert (overview["successful_requests"], overview["failed_requests"], overview["policy_blocked_requests"]) == (1, 1, 1)
    assert overview["total_requests"] == overview["successful_requests"] + overview["failed_requests"] == 2
