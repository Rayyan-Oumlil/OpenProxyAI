"""API key management route tests — list, create, revoke."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeScalarResult:
	def __init__(self, items):
		self._items = items

	def __iter__(self):
		return iter(self._items)


class FakeExecuteResult:
	def __init__(self, value):
		self._value = value

	def scalar_one(self):
		return self._value


class FakeDB:
	def __init__(self, *, scalars_result=None, get_result=None, execute_result=None, scalar_result=None, scalar_results=None):
		self._scalars_result = scalars_result
		self._get_result = get_result
		self._execute_result = execute_result
		self._scalar_result = scalar_result
		self._scalar_results = scalar_results  # list of results for multiple scalar() calls
		self._scalar_idx = 0
		self.committed = False

	async def scalars(self, *args, **kwargs):
		return FakeScalarResult(self._scalars_result or [])

	async def scalar(self, *args, **kwargs):
		if self._scalar_results is not None:
			val = self._scalar_results[self._scalar_idx]
			self._scalar_idx += 1
			return val
		if self._scalar_result is not None:
			return self._scalar_result
		return self._get_result

	async def get(self, model_cls, pk):
		return self._get_result

	async def execute(self, *args, **kwargs):
		return FakeExecuteResult(self._execute_result or 0)

	async def commit(self):
		self.committed = True

	async def refresh(self, obj):
		pass


def _make_user(org_id=None, role="admin"):
	oid = org_id or uuid4()
	return SimpleNamespace(
		id=uuid4(), org_id=oid, email="admin@test.com", is_active=True, role=role
	), oid


def _fake_api_key(org_id, user_id=None, team_id=None):
	return SimpleNamespace(
		id=uuid4(),
		org_id=org_id,
		user_id=user_id or uuid4(),
		team_id=team_id,
		name="my-key",
		key_prefix="opai_test",
		permissions=["proxy:llm"],
		is_active=True,
		expires_at=None,
		created_at=datetime.now(UTC),
	)


def _override_auth(user):
	async def dep():
		return user
	app.dependency_overrides[get_current_user_from_jwt] = dep


def _override_db(db_instance):
	async def dep():
		yield db_instance
	app.dependency_overrides[get_db] = dep


# ---------------------------------------------------------------------------
# GET /api/v1/api-keys — list API keys
# ---------------------------------------------------------------------------


def test_list_api_keys_success(client):
	user, org_id = _make_user()
	keys = [_fake_api_key(org_id, user.id), _fake_api_key(org_id, user.id)]

	_override_auth(user)
	_override_db(FakeDB(scalars_result=keys))

	response = client.get("/api/v1/api-keys", headers={"Authorization": "Bearer test"})
	assert response.status_code == 200
	data = response.json()
	assert len(data) == 2
	assert data[0]["key_prefix"] == "opai_test"
	assert data[0]["permissions"] == ["proxy:llm"]


def test_list_api_keys_empty(client):
	user, _ = _make_user()

	_override_auth(user)
	_override_db(FakeDB(scalars_result=[]))

	response = client.get("/api/v1/api-keys", headers={"Authorization": "Bearer test"})
	assert response.status_code == 200
	assert response.json() == []


def test_list_api_keys_requires_auth(client):
	response = client.get("/api/v1/api-keys")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/api-keys — create API key
# ---------------------------------------------------------------------------


def test_create_api_key_success(client, monkeypatch):
	user, org_id = _make_user()
	fake_org = SimpleNamespace(plan="pro", id=org_id)
	created_key = _fake_api_key(org_id, user.id)

	fake_db = FakeDB(get_result=fake_org, scalar_results=[None], execute_result=0)
	_override_auth(user)
	_override_db(fake_db)

	from app.routes import api_keys as api_keys_route_module
	monkeypatch.setattr(api_keys_route_module, "check_api_key_limit", lambda org, count: None)

	async def fake_create_api_key(**kwargs):
		return created_key, "opai_test_full_secret_key_1234"

	monkeypatch.setattr(api_keys_route_module, "create_api_key", fake_create_api_key)

	response = client.post(
		"/api/v1/api-keys",
		json={"name": "new-key", "permissions": ["proxy:llm"]},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 201
	data = response.json()
	assert data["key"] == "opai_test_full_secret_key_1234"
	assert data["warning"] == "Store this key securely. It will not be shown again."
	assert data["name"] == "my-key"


def test_create_api_key_requires_auth(client):
	response = client.post("/api/v1/api-keys", json={"name": "x"})
	assert response.status_code == 401


def test_create_api_key_with_team_as_member_success(client, monkeypatch):
	"""Create key with team_id when user is a member of that team."""
	user, org_id = _make_user()
	team_id = uuid4()
	fake_org = SimpleNamespace(plan="pro", id=org_id)
	fake_team = SimpleNamespace(id=team_id, org_id=org_id)
	created_key = _fake_api_key(org_id, user.id, team_id=team_id)

	# get(Organization) -> org, scalar(Team) -> team, scalar(membership) -> 1, execute(count) -> 0
	fake_db = FakeDB(
		get_result=fake_org,
		scalar_results=[fake_team, 1, None],
		execute_result=0,
	)
	_override_auth(user)
	_override_db(fake_db)

	from app.routes import api_keys as api_keys_route_module
	monkeypatch.setattr(api_keys_route_module, "check_api_key_limit", lambda org, count: None)

	async def fake_create_api_key(**kwargs):
		assert kwargs.get("team_id") == team_id
		return created_key, "opai_test_full_secret_key_1234"

	monkeypatch.setattr(api_keys_route_module, "create_api_key", fake_create_api_key)

	response = client.post(
		"/api/v1/api-keys",
		json={"name": "team-key", "permissions": ["proxy:llm"], "team_id": str(team_id)},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 201
	assert response.json()["key"] == "opai_test_full_secret_key_1234"


def test_create_api_key_with_team_not_found_returns_404(client):
	"""Create key with team_id when team does not exist or wrong org."""
	user, org_id = _make_user()
	team_id = uuid4()
	fake_org = SimpleNamespace(plan="pro", id=org_id)

	# get(Organization) -> org, scalar(Team) -> None (team not found)
	fake_db = FakeDB(
		get_result=fake_org,
		scalar_results=[None],
	)
	_override_auth(user)
	_override_db(fake_db)

	response = client.post(
		"/api/v1/api-keys",
		json={"name": "team-key", "permissions": ["proxy:llm"], "team_id": str(team_id)},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404
	assert "not found" in response.json()["detail"].lower()


def test_create_api_key_with_team_as_non_member_returns_403(client):
	"""Create key with team_id when user is NOT a member of that team."""
	user, org_id = _make_user()
	team_id = uuid4()
	fake_org = SimpleNamespace(plan="pro", id=org_id)
	fake_team = SimpleNamespace(id=team_id, org_id=org_id)

	# get(Organization) -> org, scalar(Team) -> team, scalar(membership) -> None (not member)
	fake_db = FakeDB(
		get_result=fake_org,
		scalar_results=[fake_team, None],
	)
	_override_auth(user)
	_override_db(fake_db)

	response = client.post(
		"/api/v1/api-keys",
		json={"name": "team-key", "permissions": ["proxy:llm"], "team_id": str(team_id)},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403
	assert "member" in response.json()["detail"].lower()


def test_create_api_key_validation_empty_name(client):
	user, _ = _make_user()
	_override_auth(user)
	_override_db(FakeDB())

	response = client.post(
		"/api/v1/api-keys",
		json={"name": ""},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 422


def test_create_api_key_plan_limit_exceeded(client, monkeypatch):
	user, org_id = _make_user()
	fake_org = SimpleNamespace(plan="free", id=org_id)
	fake_db = FakeDB(get_result=fake_org, scalar_results=[None], execute_result=5)
	_override_auth(user)
	_override_db(fake_db)

	from fastapi import HTTPException, status as http_status
	from app.routes import api_keys as api_keys_route_module

	def raise_limit(org, count):
		raise HTTPException(
			status_code=http_status.HTTP_402_PAYMENT_REQUIRED,
			detail={"error": "plan_limit_exceeded", "feature": "max_api_keys"},
		)

	monkeypatch.setattr(api_keys_route_module, "check_api_key_limit", raise_limit)

	response = client.post(
		"/api/v1/api-keys",
		json={"name": "another-key"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 402
	assert response.json()["detail"]["error"] == "plan_limit_exceeded"


# ---------------------------------------------------------------------------
# DELETE /api/v1/api-keys/{key_id} — revoke API key
# ---------------------------------------------------------------------------


def test_revoke_api_key_success(client):
	user, org_id = _make_user()
	key = _fake_api_key(org_id, user.id)

	fake_db = FakeDB(get_result=key)
	_override_auth(user)
	_override_db(fake_db)

	response = client.delete(
		f"/api/v1/api-keys/{key.id}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 204
	assert key.is_active is False
	assert fake_db.committed


def test_revoke_api_key_not_found(client):
	user, _ = _make_user()
	fake_db = FakeDB(get_result=None)
	_override_auth(user)
	_override_db(fake_db)

	response = client.delete(
		f"/api/v1/api-keys/{uuid4()}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404
	assert response.json()["detail"] == "API key not found"


def test_revoke_api_key_wrong_org_returns_404(client):
	"""Keys from other orgs are invisible — returns 404, not 403 (prevents IDOR enumeration)."""
	user, org_id = _make_user()

	fake_db = FakeDB(scalar_result=None)
	_override_auth(user)
	_override_db(fake_db)

	response = client.delete(
		f"/api/v1/api-keys/{uuid4()}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404
	assert response.json()["detail"] == "API key not found"


def test_revoke_api_key_requires_auth(client):
	response = client.delete(f"/api/v1/api-keys/{uuid4()}")
	assert response.status_code == 401
