"""The structured analytics query against the real schema: isolation, correctness, read-only, timeout and audit (Phase 5, slice 5.9)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, text

from app.database import org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.request_log import RequestLog
from app.models.request_score import RequestScore
from tests.db_helpers import Api, make_user, remove_seeded_logs, seed  # noqa: F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/analytics/query"


async def log(org_id, user_id, model, status=200, cost="0.01", latency=100, tokens=10):
	async with org_scoped_session(org_id) as db:
		db.add(RequestLog(
			request_id=uuid.uuid4(), org_id=org_id, user_id=user_id, model=model, provider=model.split("/")[0], status_code=status,
			cost_usd=cost, latency_ms=latency, total_tokens=tokens, prompt_tokens=tokens, error_message="a user typed this secret text",
			request_metadata={"data_class": {"class": "confidential"}, "source": "playground", "labels": {"team": "secret-team"}},
		))
		await db.commit()


@pytest.fixture
async def data(tenants):
	user = tenants.user_a
	for model, status, cost, latency in (("openai/gpt-4o", 200, "0.50", 300), ("openai/gpt-4o", 200, "0.30", 500), ("openai/gpt-4o-mini", 200, "0.02", 100), ("openai/gpt-4o-mini", 500, "0", 50)):
		await log(tenants.a, user.id, model, status, cost, latency)
	other = await make_user(tenants.b)
	await log(tenants.b, other.id, "openai/org-b-model", 200, "99.00", 9999)
	return tenants


async def query(tenants, body, role="admin"):
	async with Api(tenants.a, tenants.user_a, role=role) as api:
		return await api.http.post(PATH, json=body)


async def test_an_admin_aggregates_their_own_requests(data):
	response = await query(data, {
		"view": "requests", "select": ["model", {"agg": "count", "as": "calls"}, {"agg": "sum", "column": "cost_usd", "as": "spend"}, {"agg": "p50", "column": "latency_ms"}],
		"group_by": ["model"], "order_by": [{"column": "spend", "dir": "desc"}],
	})
	assert response.status_code == 200, response.text
	body = response.json()
	assert body["columns"] == ["model", "calls", "spend", "p50_latency_ms"]
	assert body["rows"] == [["openai/gpt-4o", 2, 0.8, 400.0], ["openai/gpt-4o-mini", 2, 0.02, 75.0]]
	assert body["row_count"] == 2 and body["truncated"] is False


async def test_another_orgs_rows_are_never_counted_even_without_a_filter(data):
	body = (await query(data, {"view": "requests", "select": [{"agg": "count"}, {"agg": "max", "column": "cost_usd"}]})).json()
	assert body["rows"] == [[4, 0.5]]  # org B's 99.00 request is not here
	models = (await query(data, {"view": "requests", "select": ["model"], "limit": 100})).json()["rows"]
	assert ["openai/org-b-model"] not in models


async def test_filters_and_the_default_window_apply(data):
	body = (await query(data, {"view": "requests", "select": [{"agg": "count"}], "where": [{"column": "status_code", "op": "=", "value": 500}]})).json()
	assert body["rows"] == [[1]]
	body = (await query(data, {"view": "requests", "select": [{"agg": "count"}], "where": [{"column": "model", "op": "in", "value": ["openai/gpt-4o", "nope"]}]})).json()
	assert body["rows"] == [[2]]
	assert (await query(data, {"view": "requests", "select": [{"agg": "count"}], "since": "2020-01-01T00:00:00Z", "until": "2020-02-01T00:00:00Z"})).json()["rows"] == [[0]]


async def test_free_text_the_users_typed_is_not_reachable_through_this_endpoint(data):
	for column in ("error_message", "request_metadata", "labels"):
		response = await query(data, {"view": "requests", "select": [column]})
		assert response.status_code == 422 and response.json()["detail"]["error"] == "invalid_query"
	everything = (await query(data, {"view": "requests", "select": ["model", "data_class", "source"], "limit": 100})).text
	assert "secret text" not in everything and "secret-team" not in everything


async def test_the_data_class_and_source_inside_the_metadata_are_queryable_as_plain_columns(data):
	body = (await query(data, {"view": "requests", "select": ["data_class", "source", {"agg": "count"}], "group_by": ["data_class", "source"]})).json()
	assert body["rows"] == [["confidential", "playground", 4]]


async def test_a_result_that_reaches_the_limit_says_it_may_be_truncated(data):
	body = (await query(data, {"view": "requests", "select": ["model"], "limit": 3})).json()
	assert body["row_count"] == 3 and body["truncated"] is True


async def test_scores_can_be_queried_too(data):
	async with org_scoped_session(data.a) as db:
		db.add_all([RequestScore(request_id=uuid.uuid4(), org_id=data.a, score_name="thumbs", value=v, comment="never returned") for v in (1, 0, 1)])
		await db.commit()
	body = (await query(data, {"view": "scores", "select": ["score_name", {"agg": "avg", "column": "value"}, {"agg": "count"}], "group_by": ["score_name"]})).json()
	assert body["rows"] == [["thumbs", 0.6667, 3]] or (body["rows"][0][0] == "thumbs" and abs(body["rows"][0][1] - 2 / 3) < 0.001)


@pytest.mark.parametrize("role", ["developer", "viewer"])
async def test_only_an_admin_may_query_or_read_the_catalog(data, role):
	assert (await query(data, {"view": "requests", "select": ["model"]}, role=role)).status_code == 403
	async with Api(data.a, data.user_a, role=role) as api:
		assert (await api.http.get(f"{PATH}/catalog")).status_code == 403


async def test_the_catalog_lists_what_can_be_asked(data):
	async with Api(data.a, data.user_a) as api:
		catalog = (await api.http.get(f"{PATH}/catalog")).json()
	views = {v["name"]: v["columns"] for v in catalog["views"]}
	assert views["requests"]["cost_usd"] == "number" and "error_message" not in views["requests"] and "comment" not in views["scores"]
	assert "p95" in catalog["aggregates"] and "in" in catalog["operators"]


async def test_every_query_is_written_to_the_admin_audit_log_without_its_rows(data):
	await query(data, {"view": "requests", "select": ["model", {"agg": "count"}], "group_by": ["model"]})
	async with org_scoped_session(data.a) as db:
		entries = (await db.scalars(select(AdminAuditLog).where(AdminAuditLog.org_id == data.a, AdminAuditLog.action == "analytics.queried"))).all()
	assert len(entries) == 1 and entries[0].after["spec"]["view"] == "requests" and "openai/gpt-4o" not in str(entries[0].after)


async def test_a_rejected_query_is_not_audited_as_run_and_a_bad_one_is_a_422_with_the_reason(data):
	response = await query(data, {"view": "requests", "select": ["model", {"agg": "count"}]})
	assert response.status_code == 422 and "group_by" in response.json()["detail"]["detail"]
	async with org_scoped_session(data.a) as db:
		assert (await db.scalar(select(func.count()).select_from(AdminAuditLog).where(AdminAuditLog.org_id == data.a, AdminAuditLog.action == "analytics.queried"))) == 0


async def test_the_transaction_the_query_runs_in_refuses_writes(data, monkeypatch):
	"""Even if a write somehow reached the executor (it cannot, by construction), the database would refuse it."""
	from app.routes import analytics_query as aq

	def sneaky(spec, org_id):
		return text("INSERT INTO request_scores (request_id, org_id, score_name, value, source) VALUES (gen_random_uuid(), :o, 'sneaky', 1, 'api')").bindparams(o=org_id), ["x"]

	monkeypatch.setattr(aq, "compile_query", sneaky)
	async with Api(data.a, data.user_a) as api:
		try:
			response = await api.http.post(PATH, json={"view": "requests", "select": [{"agg": "count"}]})
			assert response.status_code >= 500
		except Exception as exc:  # the test client re-raises server errors; the point is that the database said no
			assert "read-only" in str(exc)
	async with org_scoped_session(data.a) as db:
		assert (await db.scalar(select(func.count()).select_from(RequestScore).where(RequestScore.score_name == "sneaky"))) == 0


async def test_a_slow_query_is_cut_off_with_a_408(data, monkeypatch):
	from sqlalchemy import literal_column

	from app.routes import analytics_query as aq

	monkeypatch.setattr(aq, "STATEMENT_TIMEOUT_MS", 50)
	real = aq.compile_query

	def slow(spec, org_id):
		query_, names = real(spec, org_id)
		return query_.where(literal_column("pg_sleep(1) IS NOT NULL")), names

	monkeypatch.setattr(aq, "compile_query", slow)
	response = await query(data, {"view": "requests", "select": [{"agg": "count"}]})
	assert response.status_code == 408 and response.json()["detail"]["error"] == "query_timeout"


async def test_nothing_the_query_endpoint_does_can_write(data):
	before = await _count(data.a)
	await query(data, {"view": "requests", "select": [{"agg": "count"}]})
	assert await _count(data.a) == before


async def _count(org_id):
	async with org_scoped_session(org_id) as db:
		return await db.scalar(select(func.count()).select_from(RequestLog).where(RequestLog.org_id == org_id))
