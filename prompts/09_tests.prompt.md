# Step 9 — Test Suite

> **Reference:** Follow `prompts/01_backend_backbone.prompt.md`. Steps 2–8 complete — full backend is functional.

---

## Context

The backend works. Now lock it down with a test suite. Tests are the safety net that lets you refactor confidently. Every test must be isolated (no shared state), async, and never call real LLM APIs.

---

## What To Build This Session

### 1. Test dependencies (add to `requirements.txt`)

```
pytest==8.3.5
pytest-asyncio==0.24.0
httpx==0.28.1               # async HTTP client for FastAPI test client
pytest-mock==3.14.0         # mocker fixture (wraps unittest.mock)
factory-boy==3.3.1          # model factories to reduce fixture boilerplate
```

### 2. `backend/tests/conftest.py`

This is the most important file. Get this right before writing any tests.

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from redis.asyncio import Redis as AsyncRedis

# Test database — separate from dev database
TEST_DATABASE_URL = "postgresql+asyncpg://openproxyai:devpassword@localhost:5432/openproxyai_test"
TEST_REDIS_URL = "redis://localhost:6379/1"    # DB 1, not 0 (dev uses 0)

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """
    Each test gets its own transaction that is rolled back after the test.
    This ensures test isolation without dropping and recreating the schema.
    """
    async with test_engine.connect() as conn:
        await conn.begin_nested()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.rollback()
        await session.close()

@pytest_asyncio.fixture(scope="function")
async def redis_client():
    client = AsyncRedis.from_url(TEST_REDIS_URL, decode_responses=True)
    yield client
    await client.flushdb()    # clean Redis between tests
    await client.aclose()

@pytest_asyncio.fixture(scope="function")
async def client(db_session, redis_client):
    """
    FastAPI test client with database and Redis overridden via dependency injection.
    Uses httpx.AsyncClient with ASGITransport (no real HTTP server needed).
    """
    from app.main import app
    from app.dependencies import get_db, get_redis

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def test_org(db_session) -> Organization:
    org = Organization(
        name="Test Org",
        plan="starter",
        rate_limit_rpm=60,
        rate_limit_tpm=100_000,
        daily_budget_usd=50.0,
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org

@pytest_asyncio.fixture(scope="function")
async def test_user(db_session, test_org) -> User:
    from app.utils.crypto import hash_password
    user = User(
        email="test@example.com",
        hashed_password=hash_password("TestPassword123!"),
        org_id=test_org.id,
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def test_api_key(db_session, test_user) -> tuple[ApiKey, str]:
    """Returns (ApiKey model, full_key_string). The full key is only available here."""
    from app.utils.crypto import generate_api_key
    full_key, key_hash, key_prefix = generate_api_key(env="dev")
    api_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="Test Key",
        user_id=test_user.id,
        org_id=test_user.org_id,
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()
    return api_key, full_key

@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_api_key) -> dict[str, str]:
    _, full_key = test_api_key
    return {"Authorization": f"Bearer {full_key}"}
```

### 3. `backend/tests/test_health.py`

```python
import pytest

@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_health_response_has_request_id_header(client):
    response = await client.get("/health")
    assert "x-openproxyai-request-id" in response.headers

@pytest.mark.asyncio
async def test_health_response_has_latency_header(client):
    response = await client.get("/health")
    assert "x-openproxyai-latency-ms" in response.headers
    latency = int(response.headers["x-openproxyai-latency-ms"])
    assert latency >= 0
```

### 4. `backend/tests/test_auth.py`

```python
@pytest.mark.asyncio
async def test_register_creates_user(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "SecurePass123!",
        "org_name": "New Org",
    })
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    assert "password" not in response.json()
    assert "hashed_password" not in response.json()

@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client, test_user):
    response = await client.post("/api/v1/auth/register", json={
        "email": test_user.email,   # already exists
        "password": "SecurePass123!",
        "org_name": "Another Org",
    })
    assert response.status_code == 409

@pytest.mark.asyncio
async def test_login_returns_jwt(client, test_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "TestPassword123!",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client, test_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword",
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_create_api_key(client, auth_headers):
    response = await client.post(
        "/api/v1/keys",
        headers=auth_headers,
        json={"name": "My New Key"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"].startswith("opai_dev_")
    # Key is only shown on create; confirm it's not shown on list
    list_response = await client.get("/api/v1/keys", headers=auth_headers)
    for key in list_response.json():
        assert "key" not in key or key.get("key") is None

@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(client):
    response = await client.get(
        "/api/v1/keys",
        headers={"Authorization": "Bearer opai_dev_invalid_key"},
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_revoke_api_key(client, auth_headers, test_api_key, db_session):
    api_key, _ = test_api_key
    response = await client.delete(f"/api/v1/keys/{api_key.id}", headers=auth_headers)
    assert response.status_code == 204
    # Subsequent requests with that key should fail
    # (requires re-fetching the key from the fixture which is now revoked)
```

### 5. `backend/tests/test_proxy.py`

**Never call real LLM APIs in tests.** Mock `litellm.acompletion` and `litellm.aembedding`.

```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Helper: build a fake LiteLLM streaming response
def make_fake_stream(content="Hello from mock"):
    chunks = [
        MagicMock(
            choices=[MagicMock(delta=MagicMock(content=word, role=None))],
            usage=None,
        )
        for word in content.split()
    ]
    # Final chunk with usage stats
    final = MagicMock(
        choices=[MagicMock(delta=MagicMock(content=None, role=None))],
        usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    chunks.append(final)

    async def async_gen():
        for chunk in chunks:
            yield chunk

    return async_gen()

# Helper: build fake non-streaming response
def make_fake_response(content="Hello from mock"):
    return MagicMock(
        choices=[MagicMock(message=MagicMock(content=content, role="assistant"))],
        usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        model="gpt-4o-mini",
    )

@pytest.mark.asyncio
async def test_chat_completion_non_streaming(client, auth_headers, mocker):
    mocker.patch(
        "litellm.acompletion",
        return_value=make_fake_response(),
    )
    # Also mock cost calculation
    mocker.patch("litellm.completion_cost", return_value=0.000123)

    response = await client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["choices"][0]["message"]["content"] == "Hello from mock"
    assert "x-openproxyai-request-id" in response.headers
    assert "x-openproxyai-cost-usd" in response.headers

@pytest.mark.asyncio
async def test_chat_completion_streaming(client, auth_headers, mocker):
    mocker.patch(
        "litellm.acompletion",
        return_value=make_fake_stream("Hello from mock"),
    )
    mocker.patch("litellm.completion_cost", return_value=0.000123)

    response = await client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    # Check SSE format in body
    assert b"data: " in response.content
    assert b"[DONE]" in response.content

@pytest.mark.asyncio
async def test_chat_completion_requires_auth(client):
    response = await client.post(
        "/v1/chat/completions",
        json={"model": "openai/gpt-4o-mini", "messages": [{"role":"user","content":"hi"}]},
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_chat_completion_logs_request(client, auth_headers, mocker, db_session):
    mocker.patch("litellm.acompletion", return_value=make_fake_response())
    mocker.patch("litellm.completion_cost", return_value=0.000123)

    await client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    # Give background task a moment to write the log
    import asyncio
    await asyncio.sleep(0.1)

    result = await db_session.execute(
        select(RequestLog).order_by(RequestLog.created_at.desc()).limit(1)
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.model == "gpt-4o-mini"
    assert log.cost_usd == pytest.approx(0.000123)

@pytest.mark.asyncio
async def test_rate_limit_blocks_after_limit(client, auth_headers, mocker, redis_client, test_user):
    mocker.patch("litellm.acompletion", return_value=make_fake_response())
    mocker.patch("litellm.completion_cost", return_value=0.0)

    # Force the org's RPM limit to 1 for this test
    # (patch the org object's rate_limit_rpm attribute via mock or DB update)
    # ... depends on implementation; simplest is to set via DB:
    await db_session.execute(
        update(Organization)
        .where(Organization.id == test_user.org_id)
        .values(rate_limit_rpm=1)
    )
    await db_session.commit()

    # First call should succeed
    r1 = await client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={"model": "openai/gpt-4o-mini", "messages": [{"role":"user","content":"hi"}]},
    )
    assert r1.status_code == 200

    # Second call should be rate limited
    r2 = await client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={"model": "openai/gpt-4o-mini", "messages": [{"role":"user","content":"hi"}]},
    )
    assert r2.status_code == 429
    assert r2.json()["limit_type"] == "requests_per_minute"
```

### 6. `backend/pytest.ini`

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
filterwarnings =
    ignore::DeprecationWarning
```

---

## Done When

```bash
cd backend

# Create test database (one-time setup)
docker compose exec postgres psql -U openproxyai -c "CREATE DATABASE openproxyai_test;"

# Run all tests
pytest tests/ -v

# Expected output:
# tests/test_health.py::test_health_returns_200 PASSED
# tests/test_health.py::test_health_response_has_request_id_header PASSED
# tests/test_health.py::test_health_response_has_latency_header PASSED
# tests/test_auth.py::test_register_creates_user PASSED
# tests/test_auth.py::test_register_duplicate_email_returns_409 PASSED
# tests/test_auth.py::test_login_returns_jwt PASSED
# tests/test_auth.py::test_login_wrong_password_returns_401 PASSED
# tests/test_auth.py::test_create_api_key PASSED
# tests/test_auth.py::test_invalid_api_key_returns_401 PASSED
# tests/test_auth.py::test_revoke_api_key PASSED
# tests/test_proxy.py::test_chat_completion_non_streaming PASSED
# tests/test_proxy.py::test_chat_completion_streaming PASSED
# tests/test_proxy.py::test_chat_completion_requires_auth PASSED
# tests/test_proxy.py::test_chat_completion_logs_request PASSED
# tests/test_proxy.py::test_rate_limit_blocks_after_limit PASSED
# ========================= 15 passed in X.XXs =========================

# Verify no test touches real LLM APIs (grep for unmocked litellm calls)
grep -r "litellm" tests/ | grep -v "mocker.patch" | grep -v "import"
# Should return nothing — every litellm call must be mocked
```
