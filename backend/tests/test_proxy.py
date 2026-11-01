"""LLM proxy endpoint tests — with mocked LiteLLM (never call real APIs)."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.dependencies import get_current_user_from_api_key, get_db, get_redis, get_request_id
from app.main import app
from app.routes import proxy as proxy_routes
from app.services.policy_service import PolicyDecision
from tests.conftest import FakeDB


def _make_request(headers: dict) -> Request:
	"""Build a minimal Starlette Request from headers."""
	scope = {
		"type": "http",
		"method": "POST",
		"path": "/v1/chat/completions",
		"headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
		"query_string": b"",
	}
	return Request(scope)


@pytest.fixture(autouse=True)
def patch_policy_store(monkeypatch):
	"""Patch policy_store.load for all tests in this file that use SimpleNamespace() as db.
	Direct LLMService tests bypass the DB — use env settings-based PolicyConfig.
	"""
	from app.services.policy_service import PolicyConfig, policy_store

	async def _fake_load(org_id, db, redis):
		return PolicyConfig.from_settings()

	monkeypatch.setattr(policy_store, "load", _fake_load)


def test_chat_completions_route_success(client, fake_redis, monkeypatch):
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user)

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return fake_redis

	async def fake_get_request_id():
		return uuid4().hex

	async def fake_chat_completion(**kwargs):  # noqa: ANN003
		return JSONResponse(
			content={
				"id": "chatcmpl_test",
				"object": "chat.completion",
				"choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}],
			},
			headers={
				"X-OpenProxyAI-Provider": "openai",
				"X-OpenProxyAI-Model": "openai/gpt-4o-mini",
				"X-OpenProxyAI-Cost-USD": "0.000001",
				"X-OpenProxyAI-Gateway-Error": "false",
			},
		)

	monkeypatch.setattr(proxy_routes.llm_service, "chat_completion", fake_chat_completion)

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis
	app.dependency_overrides[get_request_id] = fake_get_request_id

	response = client.post(
		"/v1/chat/completions",
		headers={"Authorization": "Bearer opai_dev_test"},
		json={
			"model": "openai/gpt-4o-mini",
			"messages": [{"role": "user", "content": "hello"}],
		},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["object"] == "chat.completion"
	assert response.headers["x-openproxyai-provider"] == "openai"


def test_embeddings_route_success(client, fake_redis, monkeypatch):
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user)

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return fake_redis

	async def fake_get_request_id():
		return uuid4().hex

	async def fake_embedding(**kwargs):  # noqa: ANN003
		return JSONResponse(
			content={
				"object": "list",
				"data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
				"model": "text-embedding-ada-002",
			},
			headers={"X-OpenProxyAI-Provider": "openai", "X-OpenProxyAI-Gateway-Error": "false"},
		)

	monkeypatch.setattr(proxy_routes.llm_service, "embedding", fake_embedding)

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis
	app.dependency_overrides[get_request_id] = fake_get_request_id

	response = client.post(
		"/v1/embeddings",
		headers={"Authorization": "Bearer opai_dev_test"},
		json={"model": "openai/text-embedding-ada-002", "input": "hello world"},
	)

	assert response.status_code == 200
	assert response.json()["object"] == "list"


def test_chat_completions_provider_error(client, fake_redis, monkeypatch):
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user)

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return fake_redis

	async def fake_get_request_id():
		return uuid4().hex

	async def fake_chat_completion(**kwargs):  # noqa: ANN003
		return JSONResponse(
			status_code=503,
			content={"error": "no_provider_key", "detail": "No active key for provider"},
			headers={"X-OpenProxyAI-Gateway-Error": "true"},
		)

	monkeypatch.setattr(proxy_routes.llm_service, "chat_completion", fake_chat_completion)

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis
	app.dependency_overrides[get_request_id] = fake_get_request_id

	response = client.post(
		"/v1/chat/completions",
		headers={"Authorization": "Bearer opai_dev_test"},
		json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hello"}]},
	)

	assert response.status_code == 503
	assert response.json()["error"] == "no_provider_key"


def test_chat_completions_http_exception_normalized(client, fake_redis, monkeypatch):
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user)

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return fake_redis

	async def fake_get_request_id():
		return uuid4().hex

	async def fake_chat_completion(**kwargs):  # noqa: ANN003
		raise HTTPException(status_code=400, detail="bad request")

	monkeypatch.setattr(proxy_routes.llm_service, "chat_completion", fake_chat_completion)

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis
	app.dependency_overrides[get_request_id] = fake_get_request_id

	response = client.post(
		"/v1/chat/completions",
		headers={"Authorization": "Bearer opai_dev_test"},
		json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hello"}]},
	)

	assert response.status_code == 400
	assert response.json()["error"] == "gateway_error"
	assert response.headers["x-openproxyai-gateway-error"] == "true"


def test_chat_completions_preserves_http_exception_headers(client, fake_redis, monkeypatch):
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user)

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return fake_redis

	async def fake_get_request_id():
		return uuid4().hex

	async def fake_chat_completion(**kwargs):  # noqa: ANN003
		raise HTTPException(
			status_code=429,
			detail={"error": "rate_limit_exceeded", "detail": "limited", "retry_after": 5},
			headers={"Retry-After": "5", "X-RateLimit-Reset": "999"},
		)

	monkeypatch.setattr(proxy_routes.llm_service, "chat_completion", fake_chat_completion)

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis
	app.dependency_overrides[get_request_id] = fake_get_request_id

	response = client.post(
		"/v1/chat/completions",
		headers={"Authorization": "Bearer opai_dev_test"},
		json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hello"}]},
	)

	assert response.status_code == 429
	assert response.headers["retry-after"] == "5"
	assert response.headers["x-ratelimit-reset"] == "999"
	assert response.headers["x-openproxyai-gateway-error"] == "true"


@pytest.mark.asyncio
async def test_llm_service_rate_limit_contract(monkeypatch, fake_redis):
	from app.services import llm_service as llm_service_module

	request = llm_service_module.ChatCompletionRequest(
		model="openai/gpt-4o-mini",
		messages=[{"role": "user", "content": "hi"}],
	)
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("5"))
	api_key = SimpleNamespace(id=uuid4())

	async def fake_check_limits(**kwargs):  # noqa: ANN003
		return (
			False,
			{
				"X-RateLimit-Requests-Limit": "60",
				"X-RateLimit-Requests-Remaining": "0",
				"X-RateLimit-Tokens-Limit": "100000",
				"X-RateLimit-Tokens-Remaining": "0",
				"X-RateLimit-Budget-Daily-USD": "50.00",
				"X-RateLimit-Budget-Remaining-USD": "0.000000",
				"X-RateLimit-Reset": "123456",
				"Retry-After": "7",
			},
			"requests_per_minute",
			"60 requests/minute limit reached. Resets in 7 seconds.",
			7,
		)

	async def fake_log_request(**kwargs):  # noqa: ANN003
		return None

	async def fake_provider_key(*args, **kwargs):  # noqa: ANN002, ANN003
		return [(None, "dummy")]

	monkeypatch.setattr(llm_service_module.rate_limiter_service, "check_limits", fake_check_limits)
	monkeypatch.setattr(llm_service_module, "log_request", fake_log_request)
	monkeypatch.setattr(llm_service_module.llm_service, "_select_provider_keys", fake_provider_key)

	response = await llm_service_module.llm_service.chat_completion(
		request=request,
		db=FakeDB(),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=SimpleNamespace(add_task=lambda *args, **kwargs: None),
	)

	assert response.status_code == 429
	body = response.body.decode("utf-8")
	assert '"error":"rate_limit_exceeded"' in body
	assert '"limit_type":"requests_per_minute"' in body
	assert '"retry_after":7' in body
	assert response.headers["retry-after"] == "7"
	assert response.headers["x-ratelimit-requests-limit"] == "60"


@pytest.mark.asyncio
async def test_llm_service_preserves_rl_headers_on_provider_key_error(monkeypatch, fake_redis):
	from app.services import llm_service as llm_service_module

	request = llm_service_module.ChatCompletionRequest(
		model="openai/gpt-4o-mini",
		messages=[{"role": "user", "content": "hi"}],
	)
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("5"))
	api_key = SimpleNamespace(id=uuid4())

	async def fake_check_limits(**kwargs):  # noqa: ANN003
		return (
			True,
			{
				"X-RateLimit-Requests-Limit": "60",
				"X-RateLimit-Requests-Remaining": "59",
				"X-RateLimit-Tokens-Limit": "100000",
				"X-RateLimit-Tokens-Remaining": "99500",
				"X-RateLimit-Budget-Daily-USD": "50.00",
				"X-RateLimit-Budget-Remaining-USD": "49.000000",
				"X-RateLimit-Reset": "123456",
			},
			None,
			None,
			None,
		)

	async def fake_log_request(**kwargs):  # noqa: ANN003
		return None

	async def fake_provider_key(*args, **kwargs):  # noqa: ANN002, ANN003
		raise HTTPException(
			status_code=503,
			detail={"error": "no_provider_key", "detail": "No active key for provider"},
		)

	monkeypatch.setattr(llm_service_module.rate_limiter_service, "check_limits", fake_check_limits)
	monkeypatch.setattr(llm_service_module, "log_request", fake_log_request)
	monkeypatch.setattr(llm_service_module.llm_service, "_select_provider_keys", fake_provider_key)

	with pytest.raises(HTTPException) as exc_info:
		await llm_service_module.llm_service.chat_completion(
			request=request,
			db=FakeDB(),
			redis=fake_redis,
			user=user,
			api_key=api_key,
			request_id=uuid4(),
			background_tasks=SimpleNamespace(add_task=lambda *args, **kwargs: None),
		)

	exc = exc_info.value
	assert exc.status_code == 503
	assert exc.headers is not None
	assert exc.headers["X-RateLimit-Requests-Limit"] == "60"
	assert exc.headers["X-RateLimit-Reset"] == "123456"


# ---------------------------------------------------------------------------
# B2: team_id propagation — API key takes precedence over x-openproxy-team-id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_team_id_from_api_key_propagates_to_log(monkeypatch, fake_redis):
	"""When api_key has team_id and policy blocks, log_request receives team_id from key."""
	from app.services import llm_service as llm_module

	team_id = uuid4()
	captured: list[dict] = []
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("50"))
	fake_team = SimpleNamespace(id=team_id, org_id=user.org_id, budget_monthly_usd=Decimal("100"))

	class TeamFakeDB(FakeDB):
		"""Returns None for experiment query, fake_team for team query."""

		@property
		def info(self) -> dict:
			# Mirrors AsyncSession.info (set_session_org_id stores the org there).
			return self.__dict__.setdefault("_info", {})


		def __init__(self, team):
			self._scalar_results = [None, team]
			self._scalar_idx = 0

		async def scalar(self, *args, **kwargs):
			if self._scalar_idx < len(self._scalar_results):
				val = self._scalar_results[self._scalar_idx]
				self._scalar_idx += 1
				return val
			return None

		async def execute(self, *args, **kwargs):
			class RowResult:
				def first(self):
					return (1,)

			return RowResult()

	async def fake_log(**kwargs):
		captured.append(kwargs)

	async def fake_evaluate(req, cfg):
		return PolicyDecision(allowed=False, action="block", reason_code="test", detail="blocked")

	monkeypatch.setattr(llm_module, "log_request", fake_log)
	monkeypatch.setattr(llm_module.policy_service, "evaluate_chat_request", fake_evaluate)

	api_key = SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user, team_id=team_id)

	response = await llm_module.llm_service.chat_completion(
		request=llm_module.ChatCompletionRequest(
			model="openai/gpt-4o-mini",
			messages=[{"role": "user", "content": "hi"}],
		),
		db=TeamFakeDB(fake_team),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=SimpleNamespace(add_task=lambda *a, **kw: None),
		http_request=None,
	)

	assert response.status_code == 403
	assert len(captured) == 1
	assert captured[0].get("team_id") == team_id


@pytest.mark.asyncio
async def test_team_id_from_header_when_key_has_none(monkeypatch, fake_redis):
	"""When api_key has no team_id, x-openproxy-team-id header is used."""
	from app.services import llm_service as llm_module

	team_id = uuid4()
	captured: list[dict] = []
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("50"))
	fake_team = SimpleNamespace(id=team_id, org_id=user.org_id, budget_monthly_usd=Decimal("100"))

	class TeamFakeDB(FakeDB):

		@property
		def info(self) -> dict:
			# Mirrors AsyncSession.info (set_session_org_id stores the org there).
			return self.__dict__.setdefault("_info", {})

		def __init__(self, team):
			self._scalar_results = [None, team]
			self._scalar_idx = 0

		async def scalar(self, *args, **kwargs):
			if self._scalar_idx < len(self._scalar_results):
				val = self._scalar_results[self._scalar_idx]
				self._scalar_idx += 1
				return val
			return None

		async def execute(self, *args, **kwargs):
			class RowResult:
				def first(self):
					return (1,)

			return RowResult()

	async def fake_log(**kwargs):
		captured.append(kwargs)

	async def fake_evaluate(req, cfg):
		return PolicyDecision(allowed=False, action="block", reason_code="test", detail="blocked")

	monkeypatch.setattr(llm_module, "log_request", fake_log)
	monkeypatch.setattr(llm_module.policy_service, "evaluate_chat_request", fake_evaluate)

	api_key = SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user)  # no team_id

	http_request = _make_request({"x-openproxy-team-id": str(team_id)})

	response = await llm_module.llm_service.chat_completion(
		request=llm_module.ChatCompletionRequest(
			model="openai/gpt-4o-mini",
			messages=[{"role": "user", "content": "hi"}],
		),
		db=TeamFakeDB(fake_team),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=SimpleNamespace(add_task=lambda *a, **kw: None),
		http_request=http_request,
	)

	assert response.status_code == 403
	assert len(captured) == 1
	assert captured[0].get("team_id") == team_id


@pytest.mark.asyncio
async def test_team_id_from_api_key_takes_precedence_over_header(monkeypatch, fake_redis):
	"""When both api_key.team_id and header are set, api_key wins."""
	from app.services import llm_service as llm_module

	key_team_id = uuid4()
	header_team_id = uuid4()
	captured: list[dict] = []
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("50"))
	fake_team = SimpleNamespace(id=key_team_id, org_id=user.org_id, budget_monthly_usd=Decimal("100"))

	class TeamFakeDB(FakeDB):

		@property
		def info(self) -> dict:
			# Mirrors AsyncSession.info (set_session_org_id stores the org there).
			return self.__dict__.setdefault("_info", {})

		def __init__(self, team):
			self._scalar_results = [None, team]
			self._scalar_idx = 0

		async def scalar(self, *args, **kwargs):
			if self._scalar_idx < len(self._scalar_results):
				val = self._scalar_results[self._scalar_idx]
				self._scalar_idx += 1
				return val
			return None

		async def execute(self, *args, **kwargs):
			class RowResult:
				def first(self):
					return (1,)

			return RowResult()

	async def fake_log(**kwargs):
		captured.append(kwargs)

	async def fake_evaluate(req, cfg):
		return PolicyDecision(allowed=False, action="block", reason_code="test", detail="blocked")

	monkeypatch.setattr(llm_module, "log_request", fake_log)
	monkeypatch.setattr(llm_module.policy_service, "evaluate_chat_request", fake_evaluate)

	api_key = SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user, team_id=key_team_id)

	http_request = _make_request({"x-openproxy-team-id": str(header_team_id)})

	response = await llm_module.llm_service.chat_completion(
		request=llm_module.ChatCompletionRequest(
			model="openai/gpt-4o-mini",
			messages=[{"role": "user", "content": "hi"}],
		),
		db=TeamFakeDB(fake_team),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=SimpleNamespace(add_task=lambda *a, **kw: None),
		http_request=http_request,
	)

	assert response.status_code == 403
	assert len(captured) == 1
	assert captured[0].get("team_id") == key_team_id

