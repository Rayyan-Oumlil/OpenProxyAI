"""Team management API tests — CRUD, members, admin-only, org isolation."""

import pytest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.services import admin_audit_service as audit_module


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Clear dependency overrides after each test to prevent pollution."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeTeam:
	def __init__(self, org_id, name, budget_monthly_usd=None):
		self.id = uuid4()
		self.org_id = org_id
		self.name = name
		self.budget_monthly_usd = budget_monthly_usd
		self.created_at = datetime.now(UTC)


class FakeUser:
	def __init__(self, org_id, email="user@test.com", user_id=None):
		self.id = user_id or uuid4()
		self.org_id = org_id
		self.email = email
		self.name = "Test User"


class FakeScalarsResult:
	def __init__(self, items):
		self._items = items

	def __iter__(self):
		return iter(self._items)

	def all(self):
		return list(self._items)


class FakeExecuteResult:
	def __init__(self, items=None):
		self._items = items or []

	def all(self):
		return list(self._items)

	def first(self):
		return self._items[0] if self._items else None

	def scalar_one_or_none(self):
		return self._items[0] if self._items else None

	def scalar_one(self):
		return self._items[0] if self._items else 0


class FakeDB:

	@property
	def info(self) -> dict:
		# Mirrors AsyncSession.info (set_session_org_id stores the org there).
		return self.__dict__.setdefault("_info", {})

	def __init__(self, teams=None, users=None, member_counts=None):
		self._teams = list(teams or [])
		self._users = list(users or [])
		self._member_counts = member_counts or {}
		self._members: list[tuple] = []
		self.committed = False
		self.added = []
		self.deleted = []

	async def scalars(self, stmt):
		# Detect team list vs member query
		if "team_members" in str(stmt):
			if "user_id" in str(stmt):
				return FakeScalarsResult([(t, u) for t, u in self._members])
			return FakeScalarsResult([c for _, c in self._member_counts.items()])
		return FakeScalarsResult(self._teams)

	async def scalar(self, stmt):
		# Team lookup
		if "team_members" not in str(stmt):
			return self._teams[0] if self._teams else None
		# User lookup
		return self._users[0] if self._users else None

	async def execute(self, stmt):
		stmt_str = str(stmt)
		if "func.count" in stmt_str or ("COUNT" in stmt_str.upper() and "team_members" not in stmt_str):
			team_id = getattr(self._teams[0], "id", None) if self._teams else None
			count = self._member_counts.get(team_id, 0)
			return FakeExecuteResult([count])
		# list_teams: select(Team, member_counts.c.cnt) with team_members subquery
		if "team_members" in stmt_str and "teams" in stmt_str and "insert" not in stmt_str.lower():
			rows = [(t, self._member_counts.get(t.id, 0)) for t in self._teams]
			return FakeExecuteResult(rows)
		if "team_members" in stmt_str and "insert" not in stmt_str.lower():
			return FakeExecuteResult(self._members[:1] if self._members else [])
		return FakeExecuteResult()

	async def flush(self):
		pass

	def add(self, obj):
		self.added.append(obj)
		if hasattr(obj, "id") and obj.id is None:
			obj.id = uuid4()

	async def delete(self, obj):
		self.deleted.append(obj)

	async def commit(self):
		self.committed = True

	async def refresh(self, obj):
		if getattr(obj, "created_at", None) is None:
			obj.created_at = datetime.now(UTC)
		if getattr(obj, "updated_at", None) is None:
			obj.updated_at = datetime.now(UTC)


def _make_user(org_id, *, role="admin", user_id=None):
	return SimpleNamespace(
		id=user_id or uuid4(),
		org_id=org_id,
		email="admin@test.com",
		name="Admin",
		role=role,
		is_active=True,
	)


def _override_auth(user):
	async def dep():
		return user
	app.dependency_overrides[get_current_user_from_jwt] = dep


def _override_db(db_instance):
	async def dep():
		yield db_instance
	app.dependency_overrides[get_db] = dep


def _noop_audit(monkeypatch):
	async def noop_log(*args, **kwargs):
		return SimpleNamespace(id=uuid4())

	monkeypatch.setattr(audit_module, "log_admin_action", noop_log)
	monkeypatch.setattr(audit_module, "serialize_team", lambda t: {"id": str(t.id), "name": t.name})


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------


def test_list_teams_requires_auth(client):
	response = client.get("/api/v1/teams")
	assert response.status_code == 401


def test_list_teams_requires_admin(client):
	org_id = uuid4()
	user = _make_user(org_id, role="developer")
	_override_auth(user)
	_override_db(FakeDB(teams=[]))

	response = client.get("/api/v1/teams", headers={"Authorization": "Bearer test"})
	assert response.status_code == 403


def test_list_teams_success(client, monkeypatch):
	_noop_audit(monkeypatch)
	org_id = uuid4()
	user = _make_user(org_id)
	team = FakeTeam(org_id, "Engineering", Decimal("1000"))
	db = FakeDB(teams=[team], member_counts={team.id: 2})

	_override_auth(user)
	_override_db(db)

	response = client.get("/api/v1/teams", headers={"Authorization": "Bearer test"})
	assert response.status_code == 200
	data = response.json()
	assert len(data) == 1
	assert data[0]["name"] == "Engineering"
	assert data[0]["member_count"] == 2


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


def test_create_team_success(client, monkeypatch):
	_noop_audit(monkeypatch)
	org_id = uuid4()
	user = _make_user(org_id)
	db = FakeDB()

	_override_auth(user)
	_override_db(db)

	response = client.post(
		"/api/v1/teams",
		headers={"Authorization": "Bearer test"},
		json={"name": "Product", "budget_monthly_usd": 500.0},
	)
	assert response.status_code == 201
	data = response.json()
	assert data["name"] == "Product"
	assert float(data["budget_monthly_usd"]) == 500.0
	assert data["member_count"] == 0
	assert any(type(o).__name__ == "Team" for o in db.added)
	assert db.committed


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------


def test_get_team_success(client, monkeypatch):
	_noop_audit(monkeypatch)
	org_id = uuid4()
	user = _make_user(org_id)
	team = FakeTeam(org_id, "Engineering", Decimal("1000"))
	db = FakeDB(teams=[team], users=[FakeUser(org_id, "a@test.com")])

	_override_auth(user)
	_override_db(db)

	response = client.get(
		f"/api/v1/teams/{team.id}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["name"] == "Engineering"
	assert "members" in data


def test_get_team_not_found(client, monkeypatch):
	_noop_audit(monkeypatch)
	org_id = uuid4()
	user = _make_user(org_id)
	db = FakeDB(teams=[])

	_override_auth(user)
	_override_db(db)

	response = client.get(
		f"/api/v1/teams/{uuid4()}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------


def test_update_team_success(client, monkeypatch):
	_noop_audit(monkeypatch)
	org_id = uuid4()
	user = _make_user(org_id)
	team = FakeTeam(org_id, "Engineering", Decimal("1000"))
	db = FakeDB(teams=[team], member_counts={team.id: 0})

	_override_auth(user)
	_override_db(db)

	response = client.patch(
		f"/api/v1/teams/{team.id}",
		headers={"Authorization": "Bearer test"},
		json={"name": "Engineering v2", "budget_monthly_usd": 2000.0},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["name"] == "Engineering v2"
	assert float(data["budget_monthly_usd"]) == 2000.0


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


def test_delete_team_success(client, monkeypatch):
	_noop_audit(monkeypatch)
	org_id = uuid4()
	user = _make_user(org_id)
	team = FakeTeam(org_id, "Engineering")
	db = FakeDB(teams=[team])

	_override_auth(user)
	_override_db(db)

	response = client.delete(
		f"/api/v1/teams/{team.id}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 204
	assert len(db.deleted) == 1


# ---------------------------------------------------------------------------
# ADD / REMOVE MEMBERS
# ---------------------------------------------------------------------------


def test_add_member_requires_admin(client):
	org_id = uuid4()
	user = _make_user(org_id, role="developer")
	team = FakeTeam(org_id, "Engineering")
	other_user = FakeUser(org_id)
	db = FakeDB(teams=[team], users=[other_user])

	_override_auth(user)
	_override_db(db)

	response = client.post(
		f"/api/v1/teams/{team.id}/members/{other_user.id}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_remove_member_requires_admin(client):
	org_id = uuid4()
	user = _make_user(org_id, role="developer")
	team = FakeTeam(org_id, "Engineering")
	other_user = FakeUser(org_id)
	db = FakeDB(teams=[team], users=[other_user], member_counts={team.id: 1})
	db._members = [(team.id, other_user.id)]

	_override_auth(user)
	_override_db(db)

	response = client.delete(
		f"/api/v1/teams/{team.id}/members/{other_user.id}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403
