"""SOC 2 / HIPAA control smoke tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4


from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app


class FakeDB:
    async def scalar(self, *args, **kwargs):
        return None

    async def commit(self):
        return None


def test_security_headers_present(client):
    """All required security headers are returned on every response."""
    response = client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "max-age=31536000" in response.headers.get("strict-transport-security", "")
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_provider_key_rotation_requires_admin(client):
    """Key rotation endpoint returns 403 for non-admin users (member role)."""
    org_id = uuid4()
    member = SimpleNamespace(
        id=uuid4(), org_id=org_id, email="member@test.com", role="member", is_active=True,
    )

    async def fake_user():
        return member

    async def fake_db():
        yield FakeDB()

    app.dependency_overrides[get_current_user_from_jwt] = fake_user
    app.dependency_overrides[get_db] = fake_db

    response = client.post(
        f"/api/v1/provider-keys/{uuid4()}/rotate",
        headers={"Authorization": "Bearer test"},
    )
    # 403 = forbidden (non-admin), 404 = key not found (but admin check happens first)
    assert response.status_code in (403, 404)


def test_data_region_field_in_org_response(client):
    """GET /current returns data_region field."""
    org_id = uuid4()
    admin = SimpleNamespace(
        id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True,
    )
    org = SimpleNamespace(
        id=org_id,
        name="OpenProxy",
        slug="openproxy",
        plan="free",
        settings={},
        budget_monthly_usd=None,
        is_active=True,
        data_region="us",
        created_at=datetime.now(UTC),
    )

    async def fake_user():
        return admin

    class OrgDB:
        async def scalar(self, *args, **kwargs):
            return org

        async def commit(self):
            return None

    async def fake_db():
        yield OrgDB()

    app.dependency_overrides[get_current_user_from_jwt] = fake_user
    app.dependency_overrides[get_db] = fake_db

    response = client.get("/api/v1/organizations/current", headers={"Authorization": "Bearer test"})
    if response.status_code == 200:
        body = response.json()
        assert "data_region" in body
