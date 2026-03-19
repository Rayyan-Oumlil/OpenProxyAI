"""Playground API tests — prompt templates CRUD, compare endpoint, auth, org isolation."""

from datetime import datetime, UTC
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app


class FakePromptTemplate:
    def __init__(
        self,
        id=None,
        org_id=None,
        name="Test",
        description=None,
        system_message=None,
        user_template="Hello {{name}}",
        variables_schema=None,
        version=1,
        is_active=True,
        created_by=None,
        created_at=None,
        updated_at=None,
    ):
        self.id = id or uuid4()
        self.org_id = org_id or uuid4()
        self.name = name
        self.description = description
        self.system_message = system_message
        self.user_template = user_template
        self.variables_schema = variables_schema or []
        self.version = version
        self.is_active = is_active
        self.created_by = created_by
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or datetime.now(UTC)


class FakeDB:
    def __init__(self, templates=None):
        self._templates = list(templates or [])
        self._added = []
        self._committed = False

    def _scalars_result(self, items):
        class Result:
            def __iter__(_self):
                return iter(items)
        return Result()

    async def scalars(self, stmt):
        return self._scalars_result(self._templates)

    async def scalar(self, stmt):
        return self._templates[0] if self._templates else None

    def add(self, obj):
        self._added.append(obj)
        if hasattr(obj, "id") and obj.id is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        if hasattr(obj, "updated_at") and obj.updated_at is None:
            obj.updated_at = datetime.now(UTC)

    async def commit(self):
        self._committed = True
        for obj in self._added:
            if hasattr(obj, "org_id") and obj not in self._templates:
                self._templates.append(obj)

    async def get(self, model_cls, pk):
        return None

    async def refresh(self, obj):
        if hasattr(obj, "id") and obj.id is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        if hasattr(obj, "updated_at") and obj.updated_at is None:
            obj.updated_at = datetime.now(UTC)


class FakeRedis:
    _store = {}
    _counter = {}

    async def get(self, key):
        return self._store.get(key)

    async def incr(self, key):
        self._counter[key] = self._counter.get(key, 0) + 1
        return self._counter[key]

    async def expire(self, key, ttl):
        return True

    async def incrby(self, key, amount):
        self._counter[key] = self._counter.get(key, 0) + amount
        return self._counter[key]

    def pipeline(self, transaction=True):
        class Pipe:
            def __init__(s, redis):
                s._redis = redis
                s._ops = []

            def incr(s, key):
                s._ops.append(("incr", (key,), {}))
                return s

            def get(s, key):
                s._ops.append(("get", (key,), {}))
                return s

            def expire(s, key, ttl):
                s._ops.append(("expire", (key, ttl), {}))
                return s

            def incrby(s, key, amount):
                s._ops.append(("incrby", (key, amount), {}))
                return s

            async def execute(s):
                out = []
                for method, args, _ in s._ops:
                    fn = getattr(s._redis, method)
                    out.append(await fn(*args))
                return out

        return Pipe(self)


# ── Auth ────────────────────────────────────────────────────────────────────


def test_list_templates_requires_auth(client):
    response = client.get("/api/v1/prompt-templates")
    assert response.status_code == 401


def test_create_template_requires_auth(client):
    response = client.post(
        "/api/v1/prompt-templates",
        json={"name": "Test", "user_template": "Hi"},
    )
    assert response.status_code == 401


def test_compare_requires_auth(client):
    response = client.post(
        "/api/v1/playground/compare",
        json={
            "models": ["openai/gpt-4", "anthropic/claude-3-5-sonnet"],
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    assert response.status_code == 401


# ── Viewer cannot create/update/delete ──────────────────────────────────────


def test_viewer_cannot_create_template(client):
    org_id = uuid4()
    user = SimpleNamespace(id=uuid4(), org_id=org_id, role="viewer", is_active=True)

    async def fake_user():
        return user

    async def fake_db():
        yield FakeDB()

    app.dependency_overrides[get_current_user_from_jwt] = fake_user
    app.dependency_overrides[get_db] = fake_db

    response = client.post(
        "/api/v1/prompt-templates",
        headers={"Authorization": "Bearer x"},
        json={"name": "Test", "user_template": "Hi"},
    )
    assert response.status_code == 403


def test_viewer_can_list_templates(client):
    org_id = uuid4()
    user = SimpleNamespace(id=uuid4(), org_id=org_id, role="viewer", is_active=True)
    tpl = FakePromptTemplate(org_id=org_id, name="T1", user_template="x")

    async def fake_user():
        return user

    async def fake_db():
        yield FakeDB(templates=[tpl])

    app.dependency_overrides[get_current_user_from_jwt] = fake_user
    app.dependency_overrides[get_db] = fake_db

    response = client.get("/api/v1/prompt-templates", headers={"Authorization": "Bearer x"})
    assert response.status_code == 200


# ── Prompt template CRUD ─────────────────────────────────────────────────────


def test_create_template(client):
    org_id = uuid4()
    user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True)
    db = FakeDB()

    async def fake_user():
        return user

    async def fake_db():
        yield db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user
    app.dependency_overrides[get_db] = fake_db

    response = client.post(
        "/api/v1/prompt-templates",
        headers={"Authorization": "Bearer x"},
        json={
            "name": "Greeting",
            "description": "A greeting template",
            "user_template": "Hello {{name}}!",
            "variables_schema": [{"name": "name", "type": "string", "required": True}],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Greeting"
    assert data["user_template"] == "Hello {{name}}!"
    assert data["version"] == 1
    assert data["is_active"] is True


def test_list_templates_org_isolation(client):
    org_a = uuid4()
    user_a = SimpleNamespace(id=uuid4(), org_id=org_a, role="admin", is_active=True)
    tpl_a = FakePromptTemplate(org_id=org_a, name="OrgA Template", user_template="a")

    async def fake_user():
        return user_a

    async def fake_db():
        yield FakeDB(templates=[tpl_a])

    app.dependency_overrides[get_current_user_from_jwt] = fake_user
    app.dependency_overrides[get_db] = fake_db

    response = client.get("/api/v1/prompt-templates", headers={"Authorization": "Bearer x"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "OrgA Template"


# ── Compare endpoint ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_returns_results_for_all_models(client, monkeypatch):
    org_id = uuid4()
    user = SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        role="admin",
        is_active=True,
        budget_daily_usd=None,
    )

    class FakeCompletion:
        def __init__(self, model="openai/gpt-4"):
            self.model = model
            self.choices = [SimpleNamespace(message=SimpleNamespace(content="Hi from model"))]
            self.usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)

    async def fake_acompletion(**kwargs):
        return FakeCompletion(model=kwargs.get("model", "openai/gpt-4"))

    async def fake_user():
        return user

    async def fake_db():
        yield FakeDB()

    def fake_redis():
        return FakeRedis()

    async def fake_check_limits(*args, **kwargs):
        return (True, {}, None, None, None)

    async def fake_policy_load(*args, **kwargs):
        from app.services.policy_service import PolicyConfig
        return PolicyConfig()

    from app.services import rate_limiter
    from app.services import policy_service as ps

    monkeypatch.setattr("app.routes.playground.acompletion", fake_acompletion)
    app.dependency_overrides[get_current_user_from_jwt] = fake_user
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_redis] = fake_redis
    monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", fake_check_limits)
    monkeypatch.setattr(ps.policy_store, "load", fake_policy_load)

    # Need provider key for openai and anthropic - mock _select_provider_key
    async def fake_select_key(db, org_id, provider, model=None, data_region="us"):
        return "sk-fake-key"

    from app.routes import playground as pg
    monkeypatch.setattr(pg, "_select_provider_key", fake_select_key)

    # Mock log_request to avoid DB/Redis in background task
    async def noop_log(*args, **kwargs):
        pass

    monkeypatch.setattr("app.routes.playground.log_request", noop_log)

    response = client.post(
        "/api/v1/playground/compare",
        headers={"Authorization": "Bearer x"},
        json={
            "models": ["openai/gpt-4", "anthropic/claude-3-5-sonnet"],
            "messages": [{"role": "user", "content": "Say hi"}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    for r in data["results"]:
        assert "model" in r
        assert r.get("content") == "Hi from model" or r.get("error")
        assert "prompt_tokens" in r
        assert "cost_usd" in r
        assert "latency_ms" in r


def test_compare_handles_model_errors_gracefully(client, monkeypatch):
    org_id = uuid4()
    user = SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        role="developer",
        is_active=True,
        budget_daily_usd=None,
    )

    call_count = 0

    async def fake_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        if "gpt-4" in kwargs.get("model", ""):
            raise RuntimeError("API error for gpt-4")
        model = kwargs.get("model", "anthropic/claude-3-5-sonnet")
        comp = SimpleNamespace(
            model=model,
            choices=[SimpleNamespace(message=SimpleNamespace(content="Claude says hi"))],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
        )
        return comp

    async def fake_user():
        return user

    async def fake_db():
        yield FakeDB()

    def fake_redis():
        return FakeRedis()

    async def fake_check_limits(*args, **kwargs):
        return (True, {}, None, None, None)

    async def fake_policy_load(*args, **kwargs):
        from app.services.policy_service import PolicyConfig
        return PolicyConfig()

    from app.services import rate_limiter
    from app.services import policy_service as ps

    monkeypatch.setattr("app.routes.playground.acompletion", fake_acompletion)
    app.dependency_overrides[get_current_user_from_jwt] = fake_user
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_redis] = fake_redis
    monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", fake_check_limits)
    monkeypatch.setattr(ps.policy_store, "load", fake_policy_load)

    async def fake_select_key(db, org_id, provider, model=None, data_region="us"):
        return "sk-fake-key"

    from app.routes import playground as pg
    monkeypatch.setattr(pg, "_select_provider_key", fake_select_key)

    async def noop_log(*args, **kwargs):
        pass

    monkeypatch.setattr("app.routes.playground.log_request", noop_log)

    # Mock cost_tracker to avoid litellm completion_cost model format issues
    def fake_calculate_cost(_response):
        return Decimal("0.001")

    from app.services import cost_tracker
    monkeypatch.setattr(cost_tracker.cost_tracker_service, "calculate_cost_usd", fake_calculate_cost)

    response = client.post(
        "/api/v1/playground/compare",
        headers={"Authorization": "Bearer x"},
        json={
            "models": ["openai/gpt-4", "anthropic/claude-3-5-sonnet"],
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    results = data["results"]
    assert len(results) == 2
    failed = [r for r in results if r.get("error")]
    success = [r for r in results if not r.get("error") and r.get("content")]
    assert len(failed) == 1
    assert "API error" in failed[0]["error"]
    assert len(success) == 1
    assert "Claude says hi" in success[0]["content"]
