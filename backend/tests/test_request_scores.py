"""Request scores API tests — submit scores, experiment results include scores."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app


class FakeDB:
	"""Minimal AsyncSession for request scores tests."""

	def __init__(
		self,
		*,
		request_log=None,
		score_rows=None,
		execute_result=None,
	):
		self._request_log = request_log
		self._score_rows = list(score_rows or [])
		self._execute_result = execute_result
		self._added = []

	async def scalar(self, stmt):
		return self._request_log

	async def execute(self, stmt, params=None):
		if self._execute_result is not None:
			return self._execute_result
		return SimpleNamespace(rowcount=len(self._score_rows))

	async def scalars(self, stmt):
		class Result:
			def __init__(self, items):
				self._items = items

			def all(self):
				return self._items

		return Result(self._score_rows)

	async def commit(self):
		pass


@pytest.fixture
def jwt_user():
	return SimpleNamespace(
		id=uuid4(),
		org_id=uuid4(),
		email="dev@test.com",
		role="developer",
		is_active=True,
	)


def test_submit_scores_request_not_found(client, jwt_user):
	"""POST scores for non-existent request → 404."""
	async def fake_user():
		return jwt_user

	async def fake_db():
		yield FakeDB(request_log=None)

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	app.dependency_overrides[get_db] = fake_db

	response = client.post(
		f"/api/v1/requests/{uuid4()}/scores",
		headers={"Authorization": "Bearer fake-jwt"},
		json={"scores": [{"name": "coherence", "value": 4.5}]},
	)

	app.dependency_overrides.clear()
	assert response.status_code == 404
	assert "not found" in response.json().get("detail", "").lower()


def test_submit_scores_success(client, jwt_user):
	"""POST scores for existing request → 200, submitted count."""
	req_id = uuid4()
	org_id = jwt_user.org_id
	log = SimpleNamespace(
		request_id=req_id,
		org_id=org_id,
		request_metadata={
			"experiment": {
				"experiment_id": str(uuid4()),
				"variant_id": str(uuid4()),
			},
		},
	)

	async def fake_user():
		return jwt_user

	async def fake_db():
		yield FakeDB(request_log=log)

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	app.dependency_overrides[get_db] = fake_db

	response = client.post(
		f"/api/v1/requests/{req_id}/scores",
		headers={"Authorization": "Bearer fake-jwt"},
		json={
			"scores": [
				{"name": "coherence", "value": 4.5},
				{"name": "relevance", "value": 3.8},
			],
		},
	)

	app.dependency_overrides.clear()
	assert response.status_code == 200
	assert response.json()["submitted"] == 2


def test_submit_scores_invalid_empty(client, jwt_user):
	"""POST with empty scores → 422."""
	req_id = uuid4()
	log = SimpleNamespace(request_id=req_id, org_id=jwt_user.org_id, request_metadata={})

	async def fake_user():
		return jwt_user

	async def fake_db():
		yield FakeDB(request_log=log)

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	app.dependency_overrides[get_db] = fake_db

	response = client.post(
		f"/api/v1/requests/{req_id}/scores",
		headers={"Authorization": "Bearer fake-jwt"},
		json={"scores": []},
	)

	app.dependency_overrides.clear()
	assert response.status_code == 422
