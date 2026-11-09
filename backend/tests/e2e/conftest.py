"""Fixtures for end-to-end pipeline tests: real app, real Postgres + Redis, fake OpenAI upstream.

Needs DATABASE_URL (migrated to head) and REDIS_URL pointing at real services. Without them the
tests skip, unless E2E_TESTS_REQUIRED is set (CI), in which case a missing service fails the run.
"""

import asyncio
import os
import uuid
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.api_key import ApiKey
from app.models.llm_provider_key import LLMProviderKey
from app.models.organization import Organization
from app.models.user import User
from app.services.crypto_service import encrypt
from app.utils.crypto import generate_api_key, hash_password
from tests.fakes.fake_openai import FakeUpstream

_REQUIRED = bool(os.environ.get("E2E_TESTS_REQUIRED"))
_SERVICES_CONFIGURED = "postgresql" in os.environ.get("DATABASE_URL", "") and bool(os.environ.get("REDIS_URL"))

if _REQUIRED and not _SERVICES_CONFIGURED:
    raise RuntimeError("E2E_TESTS_REQUIRED is set but DATABASE_URL / REDIS_URL are not configured")

def pytest_collection_modifyitems(config, items):
    if _SERVICES_CONFIGURED:
        return
    skip = pytest.mark.skip(reason="e2e needs DATABASE_URL and REDIS_URL")
    for item in items:
        if "tests/e2e" in item.nodeid.replace(chr(92), "/"):
            item.add_marker(skip)


@dataclass
class Tenant:
    org_id: uuid.UUID
    api_key: str
    headers: dict[str, str] = field(default_factory=dict)
    admin_email: str = ""
    admin_password: str = "E2ePass1!"


@pytest.fixture(scope="session")
def upstream() -> Generator[FakeUpstream, None, None]:
    server = FakeUpstream()
    server.start()
    saved = {k: os.environ.get(k) for k in ("OPENAI_API_BASE", "OPENAI_BASE_URL")}
    os.environ["OPENAI_API_BASE"] = os.environ["OPENAI_BASE_URL"] = server.base_url
    yield server
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    server.stop()


@pytest.fixture(scope="module")
def e2e_client(upstream: FakeUpstream) -> Generator[TestClient, None, None]:
    from app.main import app
    from app.database import engine, system_engine

    # One client (one event loop) per module: pooled asyncpg connections are loop-bound, and the
    # lifespan owns the global scheduler, which must be stopped before other tests start theirs.
    with TestClient(app) as client:
        yield client
    asyncio.run(engine.dispose())
    asyncio.run(system_engine.dispose())


@pytest.fixture(autouse=True)
def _reset_upstream(upstream: FakeUpstream) -> None:
    httpx.post(f"{upstream.base_url.removesuffix('/v1')}/__reset")


def upstream_calls(upstream: FakeUpstream) -> list[dict[str, Any]]:
    return httpx.get(f"{upstream.base_url.removesuffix('/v1')}/__calls").json()


def _run(coro_factory: Callable[[AsyncSession], Any]) -> Any:
    async def runner() -> Any:
        engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await coro_factory(session)
        finally:
            await engine.dispose()

    return asyncio.run(runner())


@pytest.fixture
def make_tenant() -> Callable[..., Tenant]:
    """Create an org + admin user + proxy API key + provider keys (login role bypasses RLS)."""

    def factory(
        provider_keys: tuple[tuple[str, int], ...] = (("sk-good", 1),),
        org_settings: dict[str, Any] | None = None,
        data_region: str = "us",
    ) -> Tenant:
        full_key, key_hash, key_prefix = generate_api_key()
        suffix = uuid.uuid4().hex[:10]

        async def seed(session: AsyncSession) -> uuid.UUID:
            org = Organization(name=f"e2e-{suffix}", slug=f"e2e-{suffix}", settings=org_settings or {}, data_region=data_region)
            session.add(org)
            await session.flush()
            user = User(org_id=org.id, email=f"{suffix}@e2e.example.com", password_hash=hash_password("E2ePass1!"), role="admin", is_active=True)
            session.add(user)
            await session.flush()
            api_key_row = ApiKey(user_id=user.id, org_id=org.id, key_hash=key_hash, key_prefix=key_prefix, is_active=True)
            session.add(api_key_row)
            await session.flush()
            # Auth resolves key_hash -> org through this non-RLS table (see auth_service).
            await session.execute(
                text("INSERT INTO api_key_lookup (key_hash, org_id, api_key_id) VALUES (:h, :o, :k)"),
                {"h": key_hash, "o": org.id, "k": api_key_row.id},
            )
            for index, (raw_key, weight) in enumerate(provider_keys):
                session.add(
                    LLMProviderKey(
                        org_id=org.id,
                        provider="openai",
                        key_alias=f"fake-{index}",
                        api_key_encrypted=encrypt(raw_key),
                        weight=weight,
                        region="global",
                        model_patterns=[],
                    )
                )
            await session.commit()
            return org.id

        return Tenant(org_id=_run(seed), api_key=full_key, headers={"Authorization": f"Bearer {full_key}"}, admin_email=f"{suffix}@e2e.example.com")

    return factory


def admin_headers(client, tenant: Tenant) -> dict[str, str]:
    """Log in as the tenant's admin user (a console session, not a gateway key)."""
    response = client.post("/api/v1/auth/login", json={"email": tenant.admin_email, "password": tenant.admin_password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def fetch_request_logs(org_id: uuid.UUID) -> list[dict[str, Any]]:
    async def query(session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                "SELECT status_code, model, prompt_tokens, completion_tokens, cost_usd, error_message "
                "FROM request_logs WHERE org_id = :o ORDER BY created_at"
            ),
            {"o": org_id},
        )
        return [dict(row._mapping) for row in result]

    return _run(query)
