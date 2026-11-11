"""The structured query compiler: nothing the caller sends can become SQL text, and only allowlisted things are reachable (Phase 5, slice 5.9)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.services.query_builder import MAX_LIMIT, MAX_WINDOW_DAYS, QueryError, QuerySpec, compile_query

ORG = uuid.uuid4()


def spec(**fields):
	return QuerySpec(**{"view": "requests", "select": ["model"], **fields})


def sql(spec_: QuerySpec):
	query, names = compile_query(spec_, ORG)
	compiled = query.compile(dialect=postgresql.dialect())
	return str(compiled), compiled.params, names


def test_every_query_is_limited_to_the_callers_org_and_a_time_window():
	text, params, _ = sql(spec())
	assert "request_logs.org_id = %(org_id_1)s" in text and params["org_id_1"] == ORG
	assert "request_logs.created_at >=" in text and "request_logs.created_at <" in text and "LIMIT" in text


def test_the_window_defaults_to_thirty_days_and_a_longer_one_is_refused():
	start, end = spec().bounds()
	assert timedelta(days=29, hours=23) < end - start <= timedelta(days=30)
	now = datetime.now(UTC)
	with pytest.raises(ValidationError, match="at most"):
		spec(since=now - timedelta(days=MAX_WINDOW_DAYS + 1), until=now)
	with pytest.raises(ValidationError, match="before"):
		spec(since=now, until=now - timedelta(days=1))


def test_the_user_can_choose_columns_filters_groups_and_aggregates_from_the_allowlist():
	text, params, names = sql(spec(
		select=["model", {"agg": "count", "as": "calls"}, {"agg": "sum", "column": "cost_usd", "as": "spend"}, {"agg": "p95", "column": "latency_ms"}],
		group_by=["model"], where=[{"column": "status_code", "op": "=", "value": 200}, {"column": "provider", "op": "in", "value": ["openai", "anthropic"]}],
		order_by=[{"column": "spend", "dir": "desc"}], limit=10,
	))
	assert names == ["model", "calls", "spend", "p95_latency_ms"]
	assert "GROUP BY request_logs.model" in text and "ORDER BY spend DESC" in text and "percentile_cont" in text
	assert 200 in params.values() and ["openai", "anthropic"] in params.values()


@pytest.mark.parametrize("value", ["x'; DROP TABLE request_logs; --", "1 OR 1=1", "') UNION SELECT password_hash FROM users --", "\u0000", "wild%card"])
def test_values_are_always_bound_parameters_never_part_of_the_sql(value):
	text, params, _ = sql(spec(where=[{"column": "model", "op": "=", "value": value}]))
	assert value not in text and value in params.values()


@pytest.mark.parametrize("column", [
	"error_message", "request_metadata", "password_hash", "users.email", "model; DROP TABLE x", "model --", "MODEL", "*", "", "org_id", "request_id",
])
def test_a_column_outside_the_allowlist_is_refused_wherever_it_appears(column):
	with pytest.raises(QueryError):
		compile_query(spec(select=[column]), ORG)
	with pytest.raises(QueryError):
		compile_query(spec(where=[{"column": column, "op": "=", "value": "x"}]), ORG)
	with pytest.raises(QueryError):
		compile_query(spec(select=[{"agg": "count", "column": column}]), ORG)
	with pytest.raises(QueryError):
		compile_query(spec(select=[{"agg": "count"}], group_by=[column]), ORG)


def test_free_text_columns_a_user_typed_are_not_queryable():
	for forbidden in ("error_message", "request_metadata", "comment"):
		with pytest.raises(QueryError):
			compile_query(spec(select=[forbidden]), ORG)
	with pytest.raises(QueryError):
		compile_query(spec(view="scores", select=["comment"]), ORG)


def test_the_org_cannot_be_chosen_by_the_caller():
	for bad in ({"org_id": str(uuid.uuid4())}, {"where": [{"column": "org_id", "op": "=", "value": str(uuid.uuid4())}]}):
		with pytest.raises((ValidationError, QueryError)):
			compile_query(spec(**bad), ORG)


@pytest.mark.parametrize("fields", [
	{"view": "users"}, {"view": "request_logs"}, {"select": []}, {"limit": 0}, {"limit": MAX_LIMIT + 1}, {"surprise": 1},
	{"where": [{"column": "model", "op": "LIKE", "value": "x"}]}, {"where": [{"column": "model", "op": "=", "value": "x", "extra": 1}]},
	{"select": [{"agg": "median", "column": "latency_ms"}]}, {"select": [{"agg": "count", "as": "Bad Name"}]}, {"select": [{"agg": "count", "as": "x; drop"}]},
])
def test_unknown_views_operators_aggregates_and_fields_are_rejected_by_the_schema(fields):
	with pytest.raises((ValidationError, QueryError)):
		compile_query(spec(**fields), ORG)


def test_type_rules_are_enforced_so_a_text_column_cannot_be_summed_or_compared_by_order():
	with pytest.raises(QueryError, match="needs a number"):
		compile_query(spec(select=[{"agg": "sum", "column": "model"}]), ORG)
	with pytest.raises(QueryError, match="needs a number"):
		compile_query(spec(select=[{"agg": "avg", "column": "user_id"}]), ORG)
	with pytest.raises(QueryError, match="only be compared"):
		compile_query(spec(where=[{"column": "model", "op": ">", "value": "a"}]), ORG)
	with pytest.raises(QueryError, match="needs a column"):
		compile_query(spec(select=[{"agg": "sum"}]), ORG)


@pytest.mark.parametrize("column,value", [("status_code", "abc"), ("status_code", 1.5), ("status_code", True), ("cost_usd", "x"), ("user_id", "not-a-uuid"), ("created_at", "yesterday"), ("model", {"a": 1})])
def test_a_value_of_the_wrong_type_is_a_query_error(column, value):
	with pytest.raises((QueryError, ValidationError)):
		compile_query(spec(where=[{"column": column, "op": "=", "value": value}]), ORG)


def test_in_needs_a_bounded_list_and_other_operators_a_single_value():
	with pytest.raises(QueryError):
		compile_query(spec(where=[{"column": "model", "op": "in", "value": "single"}]), ORG)
	with pytest.raises(QueryError):
		compile_query(spec(where=[{"column": "model", "op": "in", "value": [str(i) for i in range(51)]}]), ORG)
	with pytest.raises(QueryError):
		compile_query(spec(where=[{"column": "model", "op": "=", "value": ["a", "b"]}]), ORG)


def test_grouping_rules_keep_the_result_well_formed():
	with pytest.raises(QueryError, match="group_by"):
		compile_query(spec(select=["model", {"agg": "count"}]), ORG)  # a plain column beside an aggregate must be grouped
	with pytest.raises(QueryError, match="group_by"):
		compile_query(spec(select=["model"], group_by=["model"]), ORG)  # grouping without an aggregate
	with pytest.raises(QueryError, match="group_by"):
		compile_query(spec(select=["model", {"agg": "count"}], group_by=["model", "provider"]), ORG)
	with pytest.raises(QueryError, match="twice"):
		compile_query(spec(select=["model", "model"]), ORG)


def test_order_by_can_only_name_a_selected_column_or_alias():
	with pytest.raises(QueryError, match="selected"):
		compile_query(spec(order_by=[{"column": "provider"}]), ORG)
	with pytest.raises(QueryError):
		compile_query(spec(order_by=[{"column": "1; DROP TABLE x"}]), ORG)


def test_the_scores_view_is_scoped_to_the_org_too_and_has_its_own_columns():
	text, params, _ = sql(spec(view="scores", select=["score_name", {"agg": "avg", "column": "value"}], group_by=["score_name"]))
	assert "request_scores.org_id" in text and params["org_id_1"] == ORG
	with pytest.raises(QueryError):
		compile_query(spec(view="scores", select=["model"]), ORG)


def test_the_day_column_groups_by_calendar_day():
	text, _, names = sql(spec(select=["day", {"agg": "count"}], group_by=["day"]))
	assert "date_trunc" in text and names == ["day", "count"]


def test_min_and_max_need_an_ordered_column_a_number_or_a_time():
	for agg in ("min", "max"):
		with pytest.raises(QueryError, match="number or a time"):
			compile_query(spec(select=[{"agg": agg, "column": "model"}]), ORG)
	compile_query(spec(select=[{"agg": "min", "column": "created_at"}, {"agg": "max", "column": "cost_usd"}]), ORG)
