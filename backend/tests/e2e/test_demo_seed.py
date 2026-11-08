"""The demo seed produces a working tenant: key auth, policy, console login, pinned MCP tools (P1-12)."""

import hashlib
import time

import pytest
from sqlalchemy import text

from scripts.seed_demo import ADMIN_EMAIL, ADMIN_PASSWORD, BLOCKED_KEYWORD, DEMO_API_KEY, DEMO_SLUG, INTERN_API_KEY, seed
from tests.e2e.conftest import _run, upstream_calls

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {DEMO_API_KEY}"}
INTERN_HEADERS = {"Authorization": f"Bearer {INTERN_API_KEY}"}


def _body(content: str) -> dict:
    return {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": content}]}


async def _wipe(session) -> None:
    key_hash = hashlib.sha256(DEMO_API_KEY.encode("utf-8")).hexdigest()
    await session.execute(text("DELETE FROM api_key_lookup WHERE key_hash = :h"), {"h": key_hash})
    # Logs reference the org without a cascade (they are append-only for the app role, not the login role).
    for table in ("request_logs", "admin_audit_logs"):
        await session.execute(text(f"DELETE FROM {table} WHERE org_id IN (SELECT id FROM organizations WHERE slug = :s)"), {"s": DEMO_SLUG})
    await session.execute(text("DELETE FROM organizations WHERE slug = :s"), {"s": DEMO_SLUG})
    await session.commit()


@pytest.fixture(scope="module", autouse=True)
def demo_org(e2e_client):
    _run(_wipe)
    assert _run(seed) is True
    yield
    _run(_wipe)


def test_seed_is_idempotent():
    assert _run(seed) is False


def test_seeded_key_reaches_the_upstream(e2e_client, upstream):
    response = e2e_client.post(CHAT, json=_body("hello demo"), headers=HEADERS)
    assert response.status_code == 200
    assert len(upstream_calls(upstream)) == 1


def test_seeded_policy_blocks_the_keyword_before_the_upstream(e2e_client, upstream):
    response = e2e_client.post(CHAT, json=_body(f"tell me about {BLOCKED_KEYWORD}"), headers=HEADERS)
    assert response.status_code == 446
    assert upstream_calls(upstream) == []


def test_seeded_policy_blocks_pii(e2e_client, upstream):
    response = e2e_client.post(CHAT, json=_body("my ssn is 123-45-6789"), headers=HEADERS)
    assert response.status_code == 446
    assert upstream_calls(upstream) == []


def test_seeded_admin_logs_in_and_sees_pinned_tools(e2e_client):
    login = e2e_client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert login.status_code == 200
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    servers = e2e_client.get("/api/v1/mcp-servers", headers=auth).json()
    assert [s["name"] for s in servers] == ["github"]
    assert servers[0]["pin_mode"] == "enforce"

    tools = e2e_client.get(f"/api/v1/mcp-servers/{servers[0]['id']}/tools", headers=auth).json()
    assert {t["name"]: t["status"] for t in tools} == {"search_issues": "approved", "create_issue": "pending", "deploy": "drifted"}
    deploy = next(t for t in tools if t["name"] == "deploy")
    assert "<IMPORTANT>" in deploy["definition"]["description"]
    assert "<IMPORTANT>" not in deploy["approved_snapshot"]["description"]


def test_the_intern_key_hits_its_daily_budget_after_one_expensive_request(e2e_client, upstream):
    first = e2e_client.post(CHAT, json=_body("summarise this [big-usage]"), headers=INTERN_HEADERS)
    assert first.status_code == 200

    # Spend is recorded in the background; the next request is refused once it lands.
    deadline = time.time() + 5
    second = e2e_client.post(CHAT, json=_body("and another"), headers=INTERN_HEADERS)
    while second.status_code == 200 and time.time() < deadline:
        time.sleep(0.2)
        second = e2e_client.post(CHAT, json=_body("and another"), headers=INTERN_HEADERS)

    # CLAUDE.md lists 402 for "budget exceeded", but a user's daily budget answers 429 (402 only appears on the
    # streaming pre-flight cost check). Pinned as it is today so changing it is a deliberate, visible decision.
    assert second.status_code == 429, second.text
    assert second.json()["limit_type"] == "user_budget_daily_usd"
    assert len(upstream_calls(upstream)) == 1  # the refused request never reached the provider


def test_the_admin_key_is_not_affected_by_the_intern_budget(e2e_client):
    assert e2e_client.post(CHAT, json=_body("still fine"), headers=HEADERS).status_code == 200


def test_the_drifted_mcp_tool_is_denied_without_reaching_the_server(e2e_client):
    response = e2e_client.post(
        "/v1/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "github__deploy", "arguments": {}}},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["error"]["code"] == -32004
