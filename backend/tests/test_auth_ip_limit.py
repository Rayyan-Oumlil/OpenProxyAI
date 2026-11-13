"""Auth limits are per (ip, email), so one address could still sweep many emails. A per-IP ceiling stops that."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import settings
from app.dependencies import get_db, get_redis
from app.main import app
from app.routes import auth as auth_routes


@pytest.fixture
def wired(fake_redis, monkeypatch):
    async def fake_get_db():
        yield SimpleNamespace()

    async def fake_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_redis] = fake_get_redis

    async def bad_login(**kwargs):  # noqa: ANN003
        raise HTTPException(status_code=401, detail="Invalid credentials")

    async def new_user(**kwargs):  # noqa: ANN003
        return SimpleNamespace(id=uuid4(), org_id=uuid4(), role="admin")

    monkeypatch.setattr(auth_routes, "authenticate_user", bad_login)
    monkeypatch.setattr(auth_routes, "create_user", new_user)
    monkeypatch.setattr(settings, "AUTH_IP_RATE_LIMIT_MAX_ATTEMPTS", 3, raising=False)
    monkeypatch.setattr(settings, "REGISTER_IP_RATE_LIMIT_MAX_ATTEMPTS", 3, raising=False)


def test_one_ip_cannot_sweep_many_emails_at_login(client, wired):
    codes = [
        client.post("/api/v1/auth/login", json={"email": f"user{i}@example.com", "password": "Passw0rd!x"}).status_code
        for i in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


def test_one_ip_cannot_create_unlimited_organizations(client, wired):
    codes = [
        client.post(
            "/api/v1/auth/register",
            json={"email": f"org{i}@example.com", "password": "Passw0rd!x", "name": "N", "org_name": f"Org{i}"},
        ).status_code
        for i in range(5)
    ]
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]
