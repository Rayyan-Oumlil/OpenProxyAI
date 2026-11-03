"""The demo seed produces a working tenant: key auth, policy, console login, pinned MCP tools (P1-12)."""

import hashlib

import pytest
from sqlalchemy import text

from scripts.seed_demo import ADMIN_EMAIL, ADMIN_PASSWORD, BLOCKED_KEYWORD, DEMO_API_KEY, DEMO_SLUG, seed
from tests.e2e.conftest import _run, upstream_calls

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {DEMO_API_KEY}"}


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
    assert response.status_code == 403
    assert upstream_calls(upstream) == []


def test_seeded_policy_blocks_pii(e2e_client, upstream):
    response = e2e_client.post(CHAT, json=_body("my ssn is 123-45-6789"), headers=HEADERS)
    assert response.status_code == 403
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
