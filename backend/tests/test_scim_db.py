"""SCIM against the real schema: token lifecycle, authentication, user provisioning, isolation, audit, limits.

Requires DATABASE_URL (CI sets RLS_TESTS_REQUIRED so a missing database fails instead of skipping).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.database import SystemSessionLocal, org_scoped_session
from app.dependencies import get_redis
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.api_key import ApiKey
from app.models.scim_token import ScimToken
from app.models.user import User
from app.services import scim_limits
from app.services.scim_errors import ERROR_SCHEMA
from app.services.scim_resources import PATCH_SCHEMA
from app.services.scim_tokens import issue_token
from tests.conftest import FakeRedis
from tests.db_helpers import Api
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

ADMIN_USER = "urn:ietf:params:scim:schemas:core:2.0:User"


def email() -> str:
    return f"scim-{uuid.uuid4().hex[:10]}@example.com"


async def set_plan(org_id, plan: str) -> None:
    async with SystemSessionLocal() as session:
        await session.execute(text("UPDATE organizations SET plan = :p WHERE id = :o"), {"p": plan, "o": org_id})
        await session.commit()


async def mint(org_id) -> str:
    async with org_scoped_session(org_id) as db:
        _row, plaintext, _rotated = await issue_token(db, org_id, None)
        await db.commit()
        return plaintext


async def fetch_user(org_id, user_id) -> User | None:
    async with org_scoped_session(org_id) as db:
        return await db.scalar(select(User).where(User.id == uuid.UUID(str(user_id))))


async def audit_actions(org_id) -> list[str]:
    async with org_scoped_session(org_id) as db:
        rows = await db.scalars(select(AdminAuditLog).where(AdminAuditLog.org_id == org_id).order_by(AdminAuditLog.created_at))
        return [row.action for row in rows]


@pytest.fixture
async def scim(tenants):
    """Both orgs on a plan that allows SCIM, one token each, and a client that sends them."""
    await set_plan(tenants.a, "enterprise")
    await set_plan(tenants.b, "enterprise")
    redis = FakeRedis()

    async def fake_redis():
        return redis

    app.dependency_overrides[get_redis] = fake_redis
    http = AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test")
    tokens = SimpleNamespace(a=await mint(tenants.a), b=await mint(tenants.b))

    def call(token: str | None):
        headers = {"Content-Type": "application/scim+json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        async def send(method: str, path: str, body=None, params=None):
            return await http.request(method, f"/scim/v2{path}", headers=headers, json=body, params=params)

        return send

    yield SimpleNamespace(tenants=tenants, tokens=tokens, redis=redis, http=http, a=call(tokens.a), b=call(tokens.b), call=call)
    await http.aclose()
    app.dependency_overrides.clear()


def scim_error(response, status: int, scim_type: str | None = None):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/scim+json")
    body = response.json()
    assert body["schemas"] == [ERROR_SCHEMA] and body["status"] == str(status)
    if scim_type:
        assert body["scimType"] == scim_type
    return body


def new_user(**extra) -> dict:
    return {"schemas": [ADMIN_USER], "userName": email(), "name": {"givenName": "Test", "familyName": "Person"}, "active": True, **extra}


# ── token management (admin API) ──────────────────────────────────────────────


async def test_admin_token_lifecycle_rotation_and_revocation(tenants):
    await set_plan(tenants.a, "enterprise")
    async with Api(tenants.a, tenants.user_a) as api:
        assert (await api.http.get("/api/v1/scim/token")).json()["configured"] is False

        created = await api.http.post("/api/v1/scim/token")
        assert created.status_code == 201 and created.headers["cache-control"] == "no-store"
        first = created.json()
        assert first["token"].startswith("scim_") and first["rotated"] is False and first["scim_base_url"].endswith("/scim/v2")

        shown = (await api.http.get("/api/v1/scim/token")).json()
        assert shown["configured"] is True and shown["token_prefix"] == first["token_prefix"] and "token" not in shown

        rotated = (await api.http.post("/api/v1/scim/token")).json()
        assert rotated["rotated"] is True and rotated["token"] != first["token"]

        async def whoami(token):
            return await api.http.get("/scim/v2/ServiceProviderConfig", headers={"Authorization": f"Bearer {token}"})

        scim_error(await whoami(first["token"]), 401)  # rotation stops the old token at once
        assert (await whoami(rotated["token"])).status_code == 200

        assert (await api.http.delete("/api/v1/scim/token")).status_code == 204
        scim_error(await whoami(rotated["token"]), 401)
        assert (await api.http.delete("/api/v1/scim/token")).status_code == 404
        assert (await api.http.get("/api/v1/scim/token")).json()["configured"] is False

    assert await audit_actions(tenants.a) == ["scim.token_created", "scim.token_rotated", "scim.token_revoked"]
    async with org_scoped_session(tenants.a) as db:
        entries = (await db.scalars(select(AdminAuditLog).where(AdminAuditLog.org_id == tenants.a))).all()
        assert all("scim_" + "x" not in str(e.after) and first["token"] not in str(e.after) and rotated["token"] not in str(e.after) for e in entries)


async def test_only_admins_on_a_plan_with_sso_can_manage_the_token(tenants):
    async with Api(tenants.a, tenants.user_a, role="developer") as api:
        assert (await api.http.get("/api/v1/scim/token")).status_code == 403
        assert (await api.http.post("/api/v1/scim/token")).status_code == 403
        assert (await api.http.delete("/api/v1/scim/token")).status_code == 403
    await set_plan(tenants.a, "free")
    async with Api(tenants.a, tenants.user_a) as api:
        assert (await api.http.post("/api/v1/scim/token")).status_code == 402


async def test_tokens_are_stored_hashed_and_scoped_by_row_level_security(scim):
    async with org_scoped_session(scim.tenants.a) as db:
        row = await db.scalar(select(ScimToken))
        assert row.org_id == scim.tenants.a and row.token_hash != scim.tokens.a and scim.tokens.a not in str(row.token_hash)
        assert len(row.token_hash) == 64
    async with org_scoped_session(scim.tenants.b) as db:
        assert [r.org_id for r in (await db.scalars(select(ScimToken))).all()] == [scim.tenants.b]  # A's row is invisible
        db.add(ScimToken(org_id=scim.tenants.a, token_prefix="scim_forged__", token_hash="f" * 64))
        with pytest.raises(DBAPIError):
            await db.flush()  # forging a row for another org is refused


async def test_one_live_token_per_org_is_enforced_by_the_database(scim):
    async with org_scoped_session(scim.tenants.a) as db:
        db.add(ScimToken(org_id=scim.tenants.a, token_prefix="scim_second_", token_hash="e" * 64))
        with pytest.raises(DBAPIError):
            await db.flush()


# ── authentication ────────────────────────────────────────────────────────────


async def test_bad_credentials_are_refused_with_a_scim_error(scim):
    scim_error(await scim.call(None)("GET", "/Users"), 401)
    scim_error(await scim.call("opai_" + "a" * 40)("GET", "/Users"), 401)  # a normal API key is not a SCIM token
    scim_error(await scim.call("scim_" + "a" * 43)("GET", "/Users"), 401)  # right shape, unknown
    scim_error(await scim.call("not-a-token")("GET", "/Users"), 401)
    response = await scim.http.get("/scim/v2/Users", headers={"Authorization": f"Basic {scim.tokens.a}"})
    scim_error(response, 401)
    assert response.headers["www-authenticate"] == "Bearer"


async def test_a_scim_token_opens_nothing_outside_scim(scim):
    headers = {"Authorization": f"Bearer {scim.tokens.a}"}
    assert (await scim.http.get("/api/v1/users", headers=headers)).status_code == 401
    assert (await scim.http.get("/v1/models", headers=headers)).status_code == 401
    assert (await scim.http.get("/api/v1/scim/token", headers=headers)).status_code == 401


async def test_repeated_failures_from_one_address_are_throttled(scim, monkeypatch):
    monkeypatch.setattr(scim_limits, "FAILED_ATTEMPTS_PER_WINDOW", 3)
    bad = scim.call("scim_" + "b" * 43)
    for _ in range(3):
        scim_error(await bad("GET", "/Users"), 401)
    throttled = scim_error(await bad("GET", "/Users"), 429)
    assert throttled["detail"] == "Too many failed attempts"
    scim_error(await scim.a("GET", "/Users"), 429)  # the address stays blocked for the window, even with a good token


async def test_requests_per_org_are_limited(scim, monkeypatch):
    monkeypatch.setattr(scim_limits, "ORG_REQUESTS_PER_WINDOW", 3)
    for _ in range(3):
        assert (await scim.a("GET", "/ServiceProviderConfig")).status_code == 200
    limited = await scim.a("GET", "/ServiceProviderConfig")
    scim_error(limited, 429)
    assert int(limited.headers["retry-after"]) >= 1
    assert (await scim.b("GET", "/ServiceProviderConfig")).status_code == 200  # org B has its own budget


async def test_an_org_whose_plan_does_not_include_sso_cannot_use_scim(scim):
    await set_plan(scim.tenants.a, "free")
    scim_error(await scim.a("GET", "/Users"), 403)


# ── discovery ─────────────────────────────────────────────────────────────────


async def test_discovery_documents_describe_what_is_supported(scim):
    config = (await scim.a("GET", "/ServiceProviderConfig")).json()
    assert config["patch"]["supported"] is True and config["bulk"]["supported"] is False and config["sort"]["supported"] is False
    assert config["authenticationSchemes"][0]["type"] == "oauthbearertoken"
    types = (await scim.a("GET", "/ResourceTypes")).json()
    assert [r["id"] for r in types["Resources"]] == ["User"]  # no Group resource
    schemas = (await scim.a("GET", "/Schemas")).json()
    assert schemas["Resources"][0]["id"] == ADMIN_USER
    scim_error(await scim.a("GET", "/Groups"), 404)
    scim_error(await scim.a("POST", "/Groups", {"displayName": "x"}), 404)
    scim_error(await scim.a("GET", "/Nope"), 404)


# ── users ─────────────────────────────────────────────────────────────────────


async def test_create_read_list_filter(scim):
    payload = new_user(externalId="ext-100")
    created = await scim.a("POST", "/Users", payload)
    assert created.status_code == 201 and created.headers["location"].endswith(f"/scim/v2/Users/{created.json()['id']}")
    body = created.json()
    assert body["userName"] == payload["userName"] and body["active"] is True and body["externalId"] == "ext-100"
    assert body["displayName"] == "Test Person" and body["meta"]["resourceType"] == "User"

    stored = await fetch_user(scim.tenants.a, body["id"])
    assert stored.role == "viewer" and stored.org_id == scim.tenants.a  # lowest role, the token's org
    assert stored.password_hash == "scim_provisioned"  # cannot sign in with a password

    assert (await scim.a("GET", f"/Users/{body['id']}")).json()["id"] == body["id"]
    found = (await scim.a("GET", "/Users", params={"filter": f'userName eq "{payload["userName"].upper()}"'})).json()
    assert found["totalResults"] == 1 and found["Resources"][0]["id"] == body["id"]
    by_external = (await scim.a("GET", "/Users", params={"filter": 'externalId eq "ext-100"'})).json()
    assert by_external["totalResults"] == 1
    assert (await scim.a("GET", "/Users", params={"filter": f'userName eq "{email()}"'})).json() == {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"], "totalResults": 0, "startIndex": 1, "itemsPerPage": 0, "Resources": []}
    scim_error(await scim.a("GET", "/Users", params={"filter": 'userName sw "a"'}), 400, "invalidFilter")

    everyone = (await scim.a("GET", "/Users", params={"startIndex": 1, "count": 1})).json()
    assert everyone["itemsPerPage"] == 1 and everyone["totalResults"] == 1  # only SCIM-created users are visible, not the seeded admin
    scim_error(await scim.a("GET", "/Users/not-a-uuid"), 404)
    scim_error(await scim.a("GET", f"/Users/{uuid.uuid4()}"), 404)


async def test_create_validation_and_conflicts(scim):
    scim_error(await scim.a("POST", "/Users", {"schemas": [ADMIN_USER]}), 400, "invalidValue")
    scim_error(await scim.a("POST", "/Users", {"userName": "nope"}), 400, "invalidValue")
    raw = await scim.http.post("/scim/v2/Users", content=b"{not json", headers={"Authorization": f"Bearer {scim.tokens.a}", "Content-Type": "application/scim+json"})
    scim_error(raw, 400, "invalidSyntax")

    payload = new_user(externalId="dup-1")
    assert (await scim.a("POST", "/Users", payload)).status_code == 201
    scim_error(await scim.a("POST", "/Users", payload), 409, "uniqueness")
    scim_error(await scim.a("POST", "/Users", new_user(externalId="dup-1")), 409, "uniqueness")  # same externalId, new email


async def test_patch_deactivates_and_reactivates_in_both_idp_styles(scim):
    user = (await scim.a("POST", "/Users", new_user())).json()
    okta = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "value": {"active": False}}]}
    assert (await scim.a("PATCH", f"/Users/{user['id']}", okta)).json()["active"] is False
    assert (await fetch_user(scim.tenants.a, user["id"])).is_active is False

    entra = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "Replace", "path": "active", "value": "True"}]}
    assert (await scim.a("PATCH", f"/Users/{user['id']}", entra)).json()["active"] is True
    assert (await fetch_user(scim.tenants.a, user["id"])).is_active is True

    rename = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "displayName", "value": "Renamed"}, {"op": "add", "path": "externalId", "value": "e-7"}]}
    patched = (await scim.a("PATCH", f"/Users/{user['id']}", rename)).json()
    assert patched["displayName"] == "Renamed" and patched["externalId"] == "e-7"
    cleared = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "remove", "path": "externalId"}]}
    assert "externalId" not in (await scim.a("PATCH", f"/Users/{user['id']}", cleared)).json()
    scim_error(await scim.a("PATCH", f"/Users/{user['id']}", {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "manager", "value": "x"}]}), 400, "invalidPath")


async def test_put_replaces_attributes_but_never_reenables_a_deactivated_user(scim):
    user = (await scim.a("POST", "/Users", new_user(externalId="p-1"))).json()
    assert (await scim.a("DELETE", f"/Users/{user['id']}")).status_code == 204
    replaced = await scim.a("PUT", f"/Users/{user['id']}", {"schemas": [ADMIN_USER], "userName": user["userName"], "displayName": "Via PUT"})
    assert replaced.status_code == 200
    body = replaced.json()
    assert body["displayName"] == "Via PUT" and body["active"] is False and "externalId" not in body  # omitted attributes are cleared; active untouched
    reenabled = await scim.a("PUT", f"/Users/{user['id']}", {"userName": user["userName"], "active": True})
    assert reenabled.json()["active"] is True


async def test_delete_deactivates_and_keeps_the_row(scim):
    user = (await scim.a("POST", "/Users", new_user())).json()
    assert (await scim.a("DELETE", f"/Users/{user['id']}")).status_code == 204
    assert (await scim.a("DELETE", f"/Users/{user['id']}")).status_code == 204  # idempotent
    stored = await fetch_user(scim.tenants.a, user["id"])
    assert stored is not None and stored.is_active is False
    assert (await scim.a("GET", f"/Users/{user['id']}")).json()["active"] is False
    scim_error(await scim.a("DELETE", f"/Users/{uuid.uuid4()}"), 404)


async def test_changing_the_email_checks_it_is_free(scim):
    first = (await scim.a("POST", "/Users", new_user())).json()
    second = (await scim.a("POST", "/Users", new_user())).json()
    clash = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "userName", "value": first["userName"]}]}
    scim_error(await scim.a("PATCH", f"/Users/{second['id']}", clash), 409, "uniqueness")
    free = email()
    ok = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "userName", "value": free.upper()}]}
    assert (await scim.a("PATCH", f"/Users/{second['id']}", ok)).json()["userName"] == free


# ── roles: SCIM can never grant admin ─────────────────────────────────────────


async def set_role(org_id, user_id, role: str) -> None:
    async with org_scoped_session(org_id) as db:
        user = await db.scalar(select(User).where(User.id == uuid.UUID(str(user_id))))
        user.role = role
        await db.commit()


async def test_scim_cannot_grant_or_change_roles(scim):
    scim_error(await scim.a("POST", "/Users", new_user(roles=[{"value": "admin"}])), 400, "invalidValue")
    user = (await scim.a("POST", "/Users", new_user())).json()
    for operation in ({"op": "replace", "path": "roles", "value": [{"value": "admin"}]}, {"op": "add", "value": {"roles": [{"value": "admin"}]}}):
        scim_error(await scim.a("PATCH", f"/Users/{user['id']}", {"schemas": [PATCH_SCHEMA], "Operations": [operation]}), 400, "invalidValue")
    assert (await fetch_user(scim.tenants.a, user["id"])).role == "viewer"


# ── SCIM only manages the users it created; it cannot take over anyone else ───


async def test_scim_cannot_see_or_touch_users_it_did_not_create(scim):
    """The seeded admin was created outside SCIM: invisible to it, and 404 on every verb (no email takeover of an admin)."""
    admin_id = str(scim.tenants.user_a.id)
    before = await fetch_user(scim.tenants.a, admin_id)
    takeover = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "userName", "value": email()}]}
    for method, body in (("GET", None), ("PATCH", takeover), ("PUT", {"userName": email()}), ("DELETE", None)):
        scim_error(await scim.a(method, f"/Users/{admin_id}", body), 404)
    after = await fetch_user(scim.tenants.a, admin_id)
    assert (after.email, after.is_active, after.role) == (before.email, True, "admin")
    listed = (await scim.a("GET", "/Users")).json()
    assert admin_id not in {r["id"] for r in listed["Resources"]}
    assert (await scim.a("GET", "/Users", params={"filter": f'userName eq "{before.email}"'})).json()["totalResults"] == 0
    assert (await scim.a("POST", "/Users", new_user(userName=before.email))).status_code in (400, 409)  # nor can it re-create it (the seed's .local address fails validation first)
    async with org_scoped_session(scim.tenants.a) as db:  # with a valid address the answer is the plain uniqueness conflict
        (await db.scalar(select(User).where(User.id == scim.tenants.user_a.id))).email = "seeded-admin@example.com"
        await db.commit()
    scim_error(await scim.a("POST", "/Users", new_user(userName="seeded-admin@example.com")), 409, "uniqueness")


async def test_promoted_users_cannot_be_repointed_or_reenabled_but_can_be_deactivated(scim):
    for role in ("developer", "admin"):
        user = (await scim.a("POST", "/Users", new_user())).json()
        original = user["userName"]
        await set_role(scim.tenants.a, user["id"], role)

        change = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "userName", "value": email()}]}
        scim_error(await scim.a("PATCH", f"/Users/{user['id']}", change), 403, "mutability")
        scim_error(await scim.a("PUT", f"/Users/{user['id']}", {"userName": email()}), 403, "mutability")
        assert (await fetch_user(scim.tenants.a, user["id"])).email == original
        # An unchanged email is not a change (IdPs resend it with every PUT).
        assert (await scim.a("PUT", f"/Users/{user['id']}", {"userName": original, "displayName": "Same"})).status_code == 200

        assert (await scim.a("DELETE", f"/Users/{user['id']}")).status_code == 204  # offboarding still works
        assert (await fetch_user(scim.tenants.a, user["id"])).is_active is False
        on = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "active", "value": True}]}
        scim_error(await scim.a("PATCH", f"/Users/{user['id']}", on), 403, "mutability")
        scim_error(await scim.a("PUT", f"/Users/{user['id']}", {"userName": original, "active": True}), 403, "mutability")
        assert (await fetch_user(scim.tenants.a, user["id"])).is_active is False


async def test_changing_a_viewers_email_unlinks_sso_and_revokes_api_keys(scim):
    user = (await scim.a("POST", "/Users", new_user())).json()
    uid = uuid.UUID(user["id"])
    async with org_scoped_session(scim.tenants.a) as db:
        row = await db.scalar(select(User).where(User.id == uid))
        row.sso_sub = "idp-subject-1"
        db.add(ApiKey(org_id=scim.tenants.a, user_id=uid, key_hash=uuid.uuid4().hex, key_prefix="opai_test_", name="k", is_active=True))
        await db.commit()

    other = email()
    change = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "userName", "value": other}]}
    assert (await scim.a("PATCH", f"/Users/{user['id']}", change)).json()["userName"] == other
    async with org_scoped_session(scim.tenants.a) as db:
        row = await db.scalar(select(User).where(User.id == uid))
        assert row.sso_sub is None and row.sso_connection_id is None
        assert [k.is_active for k in (await db.scalars(select(ApiKey).where(ApiKey.user_id == uid))).all()] == [False]

    # A change that does not touch the email leaves the link and keys alone.
    async with org_scoped_session(scim.tenants.a) as db:
        (await db.scalar(select(User).where(User.id == uid))).sso_sub = "idp-subject-2"
        await db.execute(text("UPDATE api_keys SET is_active = true WHERE user_id = :u"), {"u": uid})
        await db.commit()
    await scim.a("PUT", f"/Users/{user['id']}", {"userName": other, "displayName": "Renamed"})
    async with org_scoped_session(scim.tenants.a) as db:
        assert (await db.scalar(select(User).where(User.id == uid))).sso_sub == "idp-subject-2"
        assert [k.is_active for k in (await db.scalars(select(ApiKey).where(ApiKey.user_id == uid))).all()] == [True]


async def test_the_last_active_admin_cannot_be_deactivated_through_scim(scim):
    """Reachable only for a SCIM-created user an admin later promoted; the guard still holds."""
    user = (await scim.a("POST", "/Users", new_user())).json()
    await set_role(scim.tenants.a, user["id"], "admin")
    async with org_scoped_session(scim.tenants.a) as db:  # the seeded admin goes away: this is now the only active admin
        (await db.scalar(select(User).where(User.id == scim.tenants.user_a.id))).is_active = False
        await db.commit()
    body = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "active", "value": False}]}
    scim_error(await scim.a("PATCH", f"/Users/{user['id']}", body), 400, "mutability")
    scim_error(await scim.a("DELETE", f"/Users/{user['id']}"), 400, "mutability")
    assert (await fetch_user(scim.tenants.a, user["id"])).is_active is True

    async with org_scoped_session(scim.tenants.a) as db:  # with a second active admin, it may go
        (await db.scalar(select(User).where(User.id == scim.tenants.user_a.id))).is_active = True
        await db.commit()
    assert (await scim.a("DELETE", f"/Users/{user['id']}")).status_code == 204


# ── plan user limit ───────────────────────────────────────────────────────────


async def test_the_plan_user_limit_applies_to_creating_and_reenabling(scim, monkeypatch):
    from app.config import PLAN_FEATURES

    monkeypatch.setitem(PLAN_FEATURES, "enterprise", {**PLAN_FEATURES["enterprise"], "max_users": 3})  # the seeded admin + 2
    first = (await scim.a("POST", "/Users", new_user())).json()
    second = (await scim.a("POST", "/Users", new_user())).json()
    refused = scim_error(await scim.a("POST", "/Users", new_user()), 403, "tooMany")
    assert "limit" in refused["detail"].lower()

    # A deactivated user frees a seat; creating then works, and re-enabling the first now hits the limit again.
    assert (await scim.a("DELETE", f"/Users/{first['id']}")).status_code == 204
    third = (await scim.a("POST", "/Users", new_user())).json()
    on = {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "active", "value": True}]}
    scim_error(await scim.a("PATCH", f"/Users/{first['id']}", on), 403, "tooMany")
    assert (await fetch_user(scim.tenants.a, first["id"])).is_active is False
    # Deactivating is never blocked by the limit, and an inactive create needs no seat.
    assert (await scim.a("DELETE", f"/Users/{second['id']}")).status_code == 204
    assert (await scim.a("POST", "/Users", new_user(active=False))).status_code == 201
    assert third["active"] is True


# ── isolation ─────────────────────────────────────────────────────────────────


async def test_a_token_only_ever_touches_its_own_org(scim):
    mine = (await scim.a("POST", "/Users", new_user(externalId="shared-ext"))).json()
    theirs = (await scim.b("POST", "/Users", new_user(externalId="shared-ext"))).json()  # externalId is unique per org, not globally

    for method, body in (("GET", None), ("DELETE", None), ("PATCH", {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "active", "value": False}]}), ("PUT", {"userName": email()})):
        scim_error(await scim.b(method, f"/Users/{mine['id']}", body), 404)
    assert (await fetch_user(scim.tenants.a, mine["id"])).is_active is True  # untouched

    org_b_list = (await scim.b("GET", "/Users")).json()
    ids = {r["id"] for r in org_b_list["Resources"]}
    assert theirs["id"] in ids and mine["id"] not in ids and scim.tenants.user_a.id.hex not in {i.replace("-", "") for i in ids}
    assert (await scim.b("GET", "/Users", params={"filter": f'userName eq "{mine["userName"]}"'})).json()["totalResults"] == 0
    assert (await scim.b("GET", "/Users", params={"filter": f'id eq "{mine["id"]}"'})).json()["totalResults"] == 0


async def test_an_email_that_exists_in_another_org_is_a_plain_conflict(scim):
    mine = (await scim.a("POST", "/Users", new_user())).json()
    # users.email is unique across all orgs (a database rule), so org B cannot create it; the answer says only "in use".
    refused = scim_error(await scim.b("POST", "/Users", new_user(userName=mine["userName"])), 409, "uniqueness")
    assert "org" not in refused["detail"].lower()


# ── audit ─────────────────────────────────────────────────────────────────────


async def test_every_change_is_in_the_admin_audit_log_with_the_token_as_actor(scim):
    user = (await scim.a("POST", "/Users", new_user())).json()
    await scim.a("PATCH", f"/Users/{user['id']}", {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "displayName", "value": "N"}]})
    await scim.a("PATCH", f"/Users/{user['id']}", {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "active", "value": False}]})
    await scim.a("PATCH", f"/Users/{user['id']}", {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "active", "value": True}]})
    assert (await audit_actions(scim.tenants.a))[-4:] == ["user.scim_created", "user.scim_updated", "user.scim_deactivated", "user.scim_reactivated"]
    async with org_scoped_session(scim.tenants.a) as db:
        entry = await db.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "user.scim_deactivated"))
        assert entry.actor_id is None and entry.actor_email == f"scim:{scim.tokens.a[:12]}" and entry.resource_id == user["id"]
        assert entry.before["is_active"] is True and entry.after["is_active"] is False
        assert scim.tokens.a not in str(entry.before) + str(entry.after) + entry.actor_email  # the token is never written down
    assert await audit_actions(scim.tenants.b) == []  # org B saw nothing of it


async def test_a_deactivated_user_loses_access_at_once(scim):
    """Deactivation works through the same is_active check the console and the proxy already make on every request."""
    from app.services.auth_service import create_access_token

    user = (await scim.a("POST", "/Users", new_user())).json()
    token = create_access_token(str(user["id"]), str(scim.tenants.a), "viewer")
    headers = {"Authorization": f"Bearer {token}"}
    assert (await scim.http.get("/api/v1/users", headers=headers)).status_code == 200
    await scim.a("DELETE", f"/Users/{user['id']}")
    assert (await scim.http.get("/api/v1/users", headers=headers)).status_code == 401
    await scim.a("PATCH", f"/Users/{user['id']}", {"schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "active", "value": True}]})
    assert (await scim.http.get("/api/v1/users", headers=headers)).status_code == 200
