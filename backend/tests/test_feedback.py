"""POST /v1/feedback (Phase 3, slice 1): an application scores an answer with its API key."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.dependencies import get_current_user_from_api_key, get_db
from app.main import app


class FakeDB:
	"""An AsyncSession double that returns one request log and records every score insert."""

	def __init__(self, request_log=None):
		self._request_log = request_log
		self.score_inserts: list[dict] = []
		self.info: dict = {}
		self.commits = 0

	async def scalar(self, stmt):
		return self._request_log

	async def execute(self, stmt, params=None):
		table = getattr(stmt, "table", None)
		if table is not None and table.name == "request_scores":
			self.score_inserts.append(stmt.compile(dialect=postgresql.dialect()).params)
		return SimpleNamespace(rowcount=1)

	async def commit(self):
		self.commits += 1


def make_user():
	return SimpleNamespace(id=uuid4(), org_id=uuid4(), email="dev@test.com", role="developer", is_active=True)


def make_key(permissions=("proxy:llm",)):
	return SimpleNamespace(id=uuid4(), permissions=list(permissions))


def make_log(user, request_id=None, metadata=None):
	return SimpleNamespace(request_id=request_id or uuid4(), org_id=user.org_id, request_metadata=metadata or {})


@pytest.fixture
def feedback(client):
	"""Call POST /v1/feedback as an API-key user; returns (response, db)."""

	def send(body, *, log="auto", permissions=("proxy:llm",)):
		user = make_user()
		db = FakeDB(request_log=make_log(user) if log == "auto" else log)

		async def fake_auth():
			return user, make_key(permissions)

		async def fake_db():
			yield db

		app.dependency_overrides[get_current_user_from_api_key] = fake_auth
		app.dependency_overrides[get_db] = fake_db
		try:
			response = client.post("/v1/feedback", headers={"Authorization": "Bearer opai_test"}, json=body)
		finally:
			app.dependency_overrides.clear()
		return response, db, user

	return send


def body(**overrides):
	return {"request_id": str(uuid4()), "thumbs": "up", **overrides}


def test_a_request_without_an_api_key_is_refused(client):
	assert client.post("/v1/feedback", json=body()).status_code == 401


def test_thumbs_up_is_stored_as_one_under_the_default_score_name(feedback):
	response, db, user = feedback(body(thumbs="up"))
	assert response.status_code == 200
	assert response.json()["score_name"] == "thumbs" and response.json()["value"] == 1.0
	[row] = db.score_inserts
	assert (row["score_name"], float(row["value"]), row["source"], row["org_id"], row["user_id"]) == ("thumbs", 1.0, "api", user.org_id, user.id)
	assert db.commits == 1


def test_thumbs_down_is_zero_so_the_mean_is_a_satisfaction_rate(feedback):
	response, db, _ = feedback(body(thumbs="down"))
	assert response.status_code == 200 and float(db.score_inserts[0]["value"]) == 0.0


def test_a_numeric_value_with_its_own_score_name(feedback):
	response, db, _ = feedback({"request_id": str(uuid4()), "score_name": "coherence", "value": 4.5})
	assert response.status_code == 200
	assert (db.score_inserts[0]["score_name"], float(db.score_inserts[0]["value"])) == ("coherence", 4.5)


@pytest.mark.parametrize(
	"payload",
	[
		{"thumbs": "up", "value": 1},  # both
		{},  # neither
		{"thumbs": "sideways"},
		{"value": 4.5},  # a number needs a name; only thumbs has a default
		{"thumbs": "up", "surprise": 1},  # unknown field
		{"value": 1_000_000},  # outside what the column holds
		{"value": -1_000_000},
		{"value": 1, "score_name": ""},
		{"value": 1, "score_name": "has space"},
		{"value": 1, "score_name": "x" * 101},
		{"thumbs": "up", "comment": "x" * 2001},
		{"thumbs": "up", "request_id": "not-a-uuid"},
	],
)
def test_malformed_feedback_is_rejected_before_anything_is_stored(feedback, payload):
	base = {"request_id": str(uuid4())}
	response, db, _ = feedback({**base, **payload})
	assert response.status_code == 422 and db.score_inserts == []


def test_a_comment_is_redacted_of_pii_before_it_is_stored(feedback):
	response, db, _ = feedback(body(comment="Wrong answer, call me at jane.doe@example.com about SSN 123-45-6789"))
	assert response.status_code == 200
	stored = db.score_inserts[0]["comment"]
	assert "jane.doe@example.com" not in stored and "123-45-6789" not in stored and "[REDACTED]" in stored


def test_feedback_without_a_comment_stores_none(feedback):
	_, db, _ = feedback(body())
	assert db.score_inserts[0]["comment"] is None


def test_an_unknown_or_other_org_request_is_a_404_with_nothing_stored(feedback):
	response, db, _ = feedback(body(), log=None)
	assert response.status_code == 404 and db.score_inserts == []


def test_a_key_without_the_llm_permission_is_refused(feedback):
	response, db, _ = feedback(body(), permissions=("proxy:mcp",))
	assert response.status_code == 403 and db.score_inserts == []


def test_feedback_on_an_experiment_request_is_linked_to_its_variant(feedback):
	experiment_id, variant_id = uuid4(), uuid4()
	user = make_user()
	log = make_log(user, metadata={"experiment": {"experiment_id": str(experiment_id), "variant_id": str(variant_id)}})
	response, db, _ = feedback(body(request_id=str(log.request_id)), log=log)
	assert response.status_code == 200
	assert (db.score_inserts[0]["experiment_id"], db.score_inserts[0]["variant_id"]) == (experiment_id, variant_id)


def test_sending_the_same_feedback_again_is_an_upsert_not_an_error(feedback):
	request_id = str(uuid4())
	first, db1, _ = feedback(body(request_id=request_id, thumbs="up"))
	second, db2, _ = feedback(body(request_id=request_id, thumbs="down"))
	assert first.status_code == second.status_code == 200
	assert db1.score_inserts and db2.score_inserts
