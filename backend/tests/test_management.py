"""Management endpoint tests — users and organization settings guardrails."""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class FakeDB:
    def __init__(self, *, scalar_result=None, scalars_results=None):
        self.scalar_result = scalar_result
        self.scalars_results = scalars_results or []
        self.committed = False

    async def scalar(self, query):  # noqa: ARG002
        return self.scalar_result

    async def scalars(self, query):  # noqa: ARG002
        rows = self.scalars_results.pop(0) if self.scalars_results else []
        return FakeScalarResult(rows)

    async def commit(self):
        self.committed = True

    async def refresh(self, model):  # noqa: ARG002
        return None


def _admin_user(*, org_id=None):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id or uuid4(),
        email="admin@test.com",
        name="Admin",
        role="admin",
        is_active=True,
    )


def _managed_user(*, org_id, role="developer", is_active=True):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        email="dev@test.com",
        name="Dev",
        role=role,
        budget_daily_usd=None,
        budget_monthly_usd=None,
        is_active=is_active,
        created_at=datetime.utcnow(),
    )


def _organization(*, org_id):
    return SimpleNamespace(
        id=org_id,
        name="OpenProxy",
        slug="openproxy",
        plan="free",
        settings={"timezone": "UTC"},
        budget_monthly_usd=None,
        is_active=True,
        data_region="us",
        created_at=datetime.utcnow(),
    )


def test_users_list_returns_rows(client):
    admin = _admin_user()
    row = _managed_user(org_id=admin.org_id)

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(scalars_results=[[row]])

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get("/api/v1/users", headers={"Authorization": "Bearer test"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["email"] == "dev@test.com"


def test_users_update_rejects_self_admin_removal(client):
    admin = _admin_user()
    managed = _managed_user(org_id=admin.org_id, role="admin", is_active=True)
    managed.id = admin.id

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(scalar_result=managed)

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.patch(
        f"/api/v1/users/{admin.id}",
        headers={"Authorization": "Bearer test"},
        json={"role": "viewer"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot remove your own active admin access"


def test_users_update_rejects_last_admin_removal(client):
    admin = _admin_user()
    managed = _managed_user(org_id=admin.org_id, role="admin", is_active=True)

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(scalar_result=managed, scalars_results=[[managed.id]])

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.patch(
        f"/api/v1/users/{managed.id}",
        headers={"Authorization": "Bearer test"},
        json={"is_active": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot remove the last active admin in organization"


def test_organization_update_rejects_deactivation(client):
    admin = _admin_user()
    org = _organization(org_id=admin.org_id)

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(scalar_result=org)

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.patch(
        "/api/v1/organizations/current",
        headers={"Authorization": "Bearer test"},
        json={"is_active": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Organization deactivation is not allowed from this endpoint"


def test_organization_update_merges_settings(client):
    admin = _admin_user()
    org = _organization(org_id=admin.org_id)

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(scalar_result=org)

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.patch(
        "/api/v1/organizations/current",
        headers={"Authorization": "Bearer test"},
        json={"settings": {"region": "eu"}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["timezone"] == "UTC"
    assert data["settings"]["region"] == "eu"
