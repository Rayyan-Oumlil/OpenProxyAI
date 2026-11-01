"""Analytics endpoint tests — org-scoped overview and logs responses."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.schemas.analytics import AnalyticsResponse, CacheAnalyticsResponse, CostByModel, CostByUser, DailyUsageTrend, UsageOverview
from app.schemas.logs import Page, RequestLogItem
from app.schemas.reconcile import ProviderRecord
from app.services import analytics_service as analytics_service_module
from app.services.analytics_service import AnalyticsService


class FakeDB:

	@property
	def info(self) -> dict:
		# Mirrors AsyncSession.info (set_session_org_id stores the org there).
		return self.__dict__.setdefault("_info", {})

	async def commit(self):
		return None


def test_analytics_overview_route_success(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_overview(**kwargs):  # noqa: ANN003
		assert kwargs["org_id"] == org_id
		assert kwargs["period_days"] == 30
		return AnalyticsResponse(
			overview=UsageOverview(
				period_days=30,
				total_requests=10,
				successful_requests=8,
				failed_requests=2,
				policy_blocked_requests=1,
				policy_flagged_requests=2,
				total_tokens=100,
				total_cost_usd=1.25,
				avg_latency_ms=120.0,
				avg_ttft_ms=45.0,
			),
			by_model=[
				CostByModel(model="openai/gpt-4o-mini", provider="openai", requests=10, tokens=100, cost_usd=1.25)
			],
			by_user=[
				CostByUser(user_id=user.id, email=user.email, requests=10, tokens=100, cost_usd=1.25)
			],
			by_team=[],
			daily_trend=[
				DailyUsageTrend(date="2026-03-12", requests=10, tokens=100, cost_usd=1.25, avg_latency_ms=120.0)
			],
			generated_at=datetime.now(UTC),
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_overview", fake_get_overview)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get("/api/v1/analytics/overview?period_days=30", headers={"Authorization": "Bearer test"})

	assert response.status_code == 200
	data = response.json()
	assert data["overview"]["total_requests"] == 10
	assert data["overview"]["policy_blocked_requests"] == 1
	assert data["by_model"][0]["provider"] == "openai"
	assert "by_team" in data
	assert isinstance(data["by_team"], list)


def test_analytics_cache_route_success(client, monkeypatch, fake_redis):
	"""GET /api/v1/analytics/cache returns cache metrics."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_redis(request=None):
		return fake_redis

	async def fake_get_cache_metrics(**kwargs):
		assert kwargs["org_id"] == org_id
		return CacheAnalyticsResponse(
			period_days=7,
			exact_hits=100,
			semantic_hits=50,
			misses=200,
			hit_rate=0.4286,
			estimated_savings_usd=12.34,
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_cache_metrics", fake_get_cache_metrics)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.get("/api/v1/analytics/cache?period_days=7", headers={"Authorization": "Bearer test"})

	assert response.status_code == 200
	data = response.json()
	assert data["period_days"] == 7
	assert data["exact_hits"] == 100
	assert data["semantic_hits"] == 50
	assert data["misses"] == 200
	assert data["hit_rate"] == 0.4286
	assert data["estimated_savings_usd"] == 12.34


def test_analytics_overview_includes_budget_forecast_fields(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_overview(**kwargs):  # noqa: ANN003
		return AnalyticsResponse(
			overview=UsageOverview(
				period_days=30,
				total_requests=10,
				successful_requests=8,
				failed_requests=2,
				policy_blocked_requests=1,
				policy_flagged_requests=2,
				total_tokens=100,
				total_cost_usd=1.25,
				avg_latency_ms=120.0,
				avg_ttft_ms=45.0,
				projected_month_end_cost_usd=8.75,
				forecast_basis_days=5,
			),
			by_model=[],
			by_team=[],
			by_user=[],
			daily_trend=[],
			generated_at=datetime.now(UTC),
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_overview", fake_get_overview)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get("/api/v1/analytics/overview?period_days=30", headers={"Authorization": "Bearer test"})
	assert response.status_code == 200
	data = response.json()
	assert data["overview"]["projected_month_end_cost_usd"] == 8.75
	assert data["overview"]["forecast_basis_days"] == 5


def test_analytics_logs_route_success(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_request_logs(**kwargs):  # noqa: ANN003
		assert kwargs["org_id"] == org_id
		assert kwargs["page"] == 1
		assert kwargs["page_size"] == 10
		assert kwargs["status"] == "success"
		assert kwargs["policy_action"] == "block"
		assert kwargs["policy_reason"] == "keyword"
		return Page[RequestLogItem](
			items=[
				RequestLogItem(
					id=uuid4(),
					created_at=datetime.now(UTC),
					model="openai/gpt-4o-mini",
					provider="openai",
					status="success",
					prompt_tokens=10,
					completion_tokens=5,
					total_tokens=15,
					cost_usd=0.01,
					latency_ms=120,
					ttft_ms=40,
					error_message=None,
				)
			],
			total=1,
			page=1,
			page_size=10,
			total_pages=1,
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_request_logs", fake_get_request_logs)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/logs?page=1&page_size=10&status=success&policy_action=block&policy_reason=keyword",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["total"] == 1
	assert data["items"][0]["status"] == "success"


def test_analytics_logs_session_id_filter(client, monkeypatch):
	"""session_id query param is passed through to analytics service."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	session_captured = None

	async def fake_get_request_logs(**kwargs):  # noqa: ANN003
		nonlocal session_captured
		session_captured = kwargs.get("session_id")
		return Page[RequestLogItem](
			items=[],
			total=0,
			page=1,
			page_size=10,
			total_pages=0,
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_request_logs", fake_get_request_logs)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/logs?session_id=my-session-123",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	assert session_captured == "my-session-123"


def test_analytics_overview_session_id_filter(client, monkeypatch):
	"""session_id query param is passed through to overview."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	session_captured = None

	async def fake_get_overview(**kwargs):  # noqa: ANN003
		nonlocal session_captured
		session_captured = kwargs.get("session_id")
		return AnalyticsResponse(
			overview=UsageOverview(
				period_days=30,
				total_requests=0,
				successful_requests=0,
				failed_requests=0,
				policy_blocked_requests=0,
				policy_flagged_requests=0,
				total_tokens=0,
				total_cost_usd=Decimal("0"),
				avg_latency_ms=0.0,
				avg_ttft_ms=0.0,
			),
			by_model=[],
			by_user=[],
			by_team=[],
			daily_trend=[],
			generated_at=datetime.now(UTC),
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_overview", fake_get_overview)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/overview?session_id=trace-xyz",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	assert session_captured == "trace-xyz"


def test_analytics_overview_requires_auth(client):
	response = client.get("/api/v1/analytics/overview")
	assert response.status_code == 401


def test_analytics_policy_route_success(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_policy_summary(**kwargs):  # noqa: ANN003
		assert kwargs["org_id"] == org_id
		assert kwargs["period_days"] == 7
		return {
			"period_days": 7,
			"total_policy_events": 4,
			"by_action": [
				{"action": "block", "count": 3},
				{"action": "log_only", "count": 1},
			],
			"by_reason": [
				{"reason_code": "blocked_keyword", "action": "block", "count": 3},
			],
			"generated_at": datetime.now(UTC),
		}

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_policy_summary", fake_get_policy_summary)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get("/api/v1/analytics/policy?period_days=7", headers={"Authorization": "Bearer test"})

	assert response.status_code == 200
	data = response.json()
	assert data["total_policy_events"] == 4
	assert data["by_action"][0]["action"] == "block"


def test_analytics_policy_export_json(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_policy_events(**kwargs):  # noqa: ANN003
		assert kwargs["org_id"] == org_id
		assert kwargs["period_days"] == 14
		assert kwargs["action"] == "block"
		assert kwargs["reason_code"] == "keyword"
		return [
			{
				"id": str(uuid4()),
				"request_id": str(uuid4()),
				"created_at": datetime.now(UTC).isoformat(),
				"model": "openai/gpt-4o-mini",
				"provider": "openai",
				"status_code": 403,
				"policy_action": "block",
				"policy_reason": "blocked_keyword",
				"policy_triggered_rules": ["blocked_keyword"],
			}
		], False

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_policy_events", fake_get_policy_events)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/policy/export?format=json&period_days=14&action=block&reason_code=keyword",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	assert "policy-events.json" in response.headers["content-disposition"]
	data = response.json()
	assert data["total"] == 1
	assert data["items"][0]["policy_action"] == "block"


def test_analytics_policy_export_csv(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_policy_events(**kwargs):  # noqa: ANN003
		assert kwargs["period_days"] == 7
		return [
			{
				"id": str(uuid4()),
				"request_id": str(uuid4()),
				"created_at": datetime.now(UTC).isoformat(),
				"model": "openai/gpt-4o-mini",
				"provider": "openai",
				"status_code": 200,
				"policy_action": "log_only",
				"policy_reason": "pii_detected",
				"policy_triggered_rules": ["pii_detection"],
			}
		], False

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_policy_events", fake_get_policy_events)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/policy/export?format=csv&period_days=7",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	assert response.headers["content-type"].startswith("text/csv")
	assert "policy-events.csv" in response.headers["content-disposition"]
	assert "policy_action" in response.text
	assert "log_only" in response.text


def test_analytics_compliance_export_csv(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_compliance_report_rows(**kwargs):  # noqa: ANN003
		assert kwargs["org_id"] == org_id
		assert kwargs["period_days"] == 30
		return [
			{
				"record_type": "policy_violation",
				"timestamp": datetime.now(UTC).isoformat(),
				"subject": "",
				"action": "block",
				"detail": "blocked_keyword",
				"model": "openai/gpt-4o-mini",
				"provider": "openai",
				"status": "403",
				"budget_monthly_usd": "",
				"actual_cost_period_usd": "",
			}
		]

	monkeypatch.setattr(
		analytics_service_module.analytics_service,
		"get_compliance_report_rows",
		fake_get_compliance_report_rows,
	)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/compliance/export?period_days=30",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	assert response.headers["content-type"].startswith("text/csv")
	assert "compliance-report.csv" in response.headers["content-disposition"]
	assert "record_type" in response.text
	assert "policy_violation" in response.text


def test_analytics_logs_requires_auth(client):
	response = client.get("/api/v1/analytics/logs")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# resolve_window unit tests (pure function, no DB)
# ---------------------------------------------------------------------------


def test_resolve_window_invalid_date_range():
	with pytest.raises(ValueError, match="start_date must be before or equal to end_date"):
		AnalyticsService.resolve_window(30, date(2026, 3, 10), date(2026, 3, 1))


def test_resolve_window_both_dates_explicit():
	start, end = AnalyticsService.resolve_window(30, date(2026, 3, 1), date(2026, 3, 7))
	assert start == date(2026, 3, 1)
	assert end == date(2026, 3, 7)


def test_resolve_window_same_start_and_end():
	start, end = AnalyticsService.resolve_window(30, date(2026, 3, 5), date(2026, 3, 5))
	assert start == end == date(2026, 3, 5)


def test_resolve_window_period_days_only():
	start, end = AnalyticsService.resolve_window(7, None, None)
	assert (end - start).days == 6  # 7 days inclusive


# ---------------------------------------------------------------------------
# Policy export edge cases
# ---------------------------------------------------------------------------


def test_policy_export_invalid_date_range_422(client, monkeypatch):
	"""start_date > end_date must return 422."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/policy/export?start_date=2026-03-10&end_date=2026-03-01",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 422


def test_policy_export_empty_events_json(client, monkeypatch):
	"""Empty event list returns {items: [], total: 0}."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_policy_events(**kwargs):  # noqa: ANN003
		return [], False

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_policy_events", fake_get_policy_events)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/policy/export?format=json",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["total"] == 0
	assert data["items"] == []


def test_policy_export_multi_rule_csv(client, monkeypatch):
	"""Multiple triggered_rules are joined with semicolons in CSV output."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_policy_events(**kwargs):  # noqa: ANN003
		return [
			{
				"id": str(uuid4()),
				"request_id": str(uuid4()),
				"created_at": datetime.now(UTC).isoformat(),
				"model": "openai/gpt-4o-mini",
				"provider": "openai",
				"status_code": 403,
				"policy_action": "block",
				"policy_reason": "blocked_keyword",
				"policy_triggered_rules": ["blocked_keyword", "pii_detection"],
			}
		], False

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_policy_events", fake_get_policy_events)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/policy/export?format=csv",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	assert "blocked_keyword;pii_detection" in response.text


def test_policy_export_empty_events_csv(client, monkeypatch):
	"""Empty event list returns CSV with only a header row."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_policy_events(**kwargs):  # noqa: ANN003
		return [], False

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_policy_events", fake_get_policy_events)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		"/api/v1/analytics/policy/export?format=csv",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	lines = [ln for ln in response.text.strip().splitlines() if ln]
	# Only the header row — no data rows
	assert len(lines) == 1
	assert "policy_action" in lines[0]


# ---------------------------------------------------------------------------
# Reconcile route tests
# ---------------------------------------------------------------------------


def test_reconcile_route_requires_auth(client):
	response = client.post("/api/v1/analytics/reconcile", json={"provider": "openai", "records": []})
	assert response.status_code == 401


def test_reconcile_route_empty_records_422(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.post(
		"/api/v1/analytics/reconcile",
		json={"provider": "openai", "records": []},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 422


def test_reconcile_route_returns_report(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_reconcile(**kwargs):  # noqa: ANN003
		from app.schemas.reconcile import ReconcileReport, ReconcileRowDelta, ReconcileSummary

		return ReconcileReport(
			provider="openai",
			period_start="2026-03-01",
			period_end="2026-03-01",
			total_rows=1,
			mismatch_rows=0,
			rows=[
				ReconcileRowDelta(
					date="2026-03-01",
					model="gpt-4o-mini",
					gateway_requests=10,
					provider_requests=10,
					delta_requests=0,
					pct_delta_requests=0.0,
					gateway_input_tokens=1000,
					provider_input_tokens=1000,
					delta_input_tokens=0,
					pct_delta_input_tokens=0.0,
					gateway_output_tokens=500,
					provider_output_tokens=500,
					delta_output_tokens=0,
					pct_delta_output_tokens=0.0,
					gateway_cost_usd=0.5,
					provider_cost_usd=0.5,
					delta_cost_usd=0.0,
					pct_delta_cost_usd=0.0,
				)
			],
			summary=ReconcileSummary(
				total_gateway_requests=10,
				total_provider_requests=10,
				total_delta_requests=0,
				total_gateway_input_tokens=1000,
				total_provider_input_tokens=1000,
				total_delta_input_tokens=0,
				total_gateway_output_tokens=500,
				total_provider_output_tokens=500,
				total_delta_output_tokens=0,
				total_gateway_cost_usd=0.5,
				total_provider_cost_usd=0.5,
				total_delta_cost_usd=0.0,
			),
			generated_at=datetime.now(UTC),
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "reconcile_with_provider", fake_reconcile)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.post(
		"/api/v1/analytics/reconcile",
		json={
			"provider": "openai",
			"records": [
				{
					"date": "2026-03-01",
					"model": "gpt-4o-mini",
					"requests": 10,
					"input_tokens": 1000,
					"output_tokens": 500,
					"cost_usd": 0.5,
				}
			],
		},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["provider"] == "openai"
	assert data["mismatch_rows"] == 0
	assert data["rows"][0]["delta_requests"] == 0
	assert data["summary"]["total_delta_requests"] == 0


# ---------------------------------------------------------------------------
# Reconcile service unit tests (no HTTP layer, no real DB)
# ---------------------------------------------------------------------------


class FakeExecuteResult:
	"""Minimal execute result mock for analytics_service tests."""

	def __init__(self, rows: list) -> None:
		self._rows = rows

	def mappings(self) -> "FakeExecuteResult":
		return self

	def all(self) -> list:
		return self._rows


class FakeReconcileDB:
	"""Async DB mock that returns preset rows for the reconciliation query."""

	def __init__(self, rows: list) -> None:
		self._rows = rows

	async def execute(self, *args, **kwargs) -> FakeExecuteResult:  # noqa: ANN002, ANN003
		return FakeExecuteResult(self._rows)


def _make_gw_row(d: str, model: str, requests: int, input_tokens: int, output_tokens: int, cost: str) -> dict:
	"""Build a gateway row dict with the shape returned by mv_daily_spend."""
	return {
		"date": date.fromisoformat(d),
		"model": model,
		"requests": requests,
		"input_tokens": input_tokens,
		"output_tokens": output_tokens,
		"cost_usd": Decimal(cost),
	}


@pytest.mark.asyncio
async def test_reconcile_service_exact_match():
	"""Gateway equals provider on every dimension → all deltas zero."""
	svc = AnalyticsService()
	gw = [_make_gw_row("2026-03-01", "gpt-4o-mini", 100, 5000, 2000, "1.50")]
	records = [ProviderRecord(date="2026-03-01", model="gpt-4o-mini", requests=100, input_tokens=5000, output_tokens=2000, cost_usd=1.50)]

	report = await svc.reconcile_with_provider(db=FakeReconcileDB(gw), org_id=uuid4(), provider="openai", records=records)

	assert report.total_rows == 1
	assert report.mismatch_rows == 0
	row = report.rows[0]
	assert row.delta_requests == 0
	assert row.delta_input_tokens == 0
	assert row.delta_output_tokens == 0
	assert row.pct_delta_requests == 0.0
	assert report.summary.total_delta_requests == 0
	assert report.summary.total_delta_input_tokens == 0


@pytest.mark.asyncio
async def test_reconcile_service_gateway_overcounts():
	"""Gateway > provider → positive deltas and positive pct."""
	svc = AnalyticsService()
	gw = [_make_gw_row("2026-03-01", "gpt-4o-mini", 110, 5500, 2200, "1.65")]
	records = [ProviderRecord(date="2026-03-01", model="gpt-4o-mini", requests=100, input_tokens=5000, output_tokens=2000, cost_usd=1.50)]

	report = await svc.reconcile_with_provider(db=FakeReconcileDB(gw), org_id=uuid4(), provider="openai", records=records)

	row = report.rows[0]
	assert row.delta_requests == 10
	assert row.pct_delta_requests == 10.0
	assert row.delta_input_tokens == 500
	assert row.delta_output_tokens == 200
	assert report.mismatch_rows == 1
	assert report.summary.total_delta_requests == 10


@pytest.mark.asyncio
async def test_reconcile_service_provider_overcounts():
	"""Provider > gateway → negative deltas."""
	svc = AnalyticsService()
	gw = [_make_gw_row("2026-03-01", "gpt-4o-mini", 80, 4000, 1600, "1.20")]
	records = [ProviderRecord(date="2026-03-01", model="gpt-4o-mini", requests=100, input_tokens=5000, output_tokens=2000, cost_usd=1.50)]

	report = await svc.reconcile_with_provider(db=FakeReconcileDB(gw), org_id=uuid4(), provider="openai", records=records)

	row = report.rows[0]
	assert row.delta_requests == -20
	assert row.pct_delta_requests == -20.0
	assert report.mismatch_rows == 1


@pytest.mark.asyncio
async def test_reconcile_service_provider_only_row():
	"""Row exists in provider but not in gateway → gateway values are zero."""
	svc = AnalyticsService()
	records = [ProviderRecord(date="2026-03-01", model="gpt-4o-mini", requests=50, input_tokens=2500, output_tokens=1000, cost_usd=0.75)]

	# Gateway returns nothing for this date/model
	report = await svc.reconcile_with_provider(db=FakeReconcileDB([]), org_id=uuid4(), provider="openai", records=records)

	assert report.total_rows == 1
	assert report.mismatch_rows == 1
	row = report.rows[0]
	assert row.gateway_requests == 0
	assert row.provider_requests == 50
	assert row.delta_requests == -50
	# provider = 50 (non-zero), so pct = (0 - 50) / 50 * 100 = -100.0
	assert row.pct_delta_requests == -100.0


@pytest.mark.asyncio
async def test_reconcile_service_gateway_only_row():
	"""Row exists in gateway but not in provider → provider values are zero, pct is None."""
	svc = AnalyticsService()
	gw = [_make_gw_row("2026-03-01", "gpt-4o-mini", 60, 3000, 1200, "0.90")]
	# Provider sends a different model so gpt-4o-mini is gateway-only
	records = [ProviderRecord(date="2026-03-01", model="gpt-4o", requests=5, input_tokens=100, output_tokens=50, cost_usd=0.10)]

	report = await svc.reconcile_with_provider(db=FakeReconcileDB(gw), org_id=uuid4(), provider="openai", records=records)

	assert report.total_rows == 2
	gw_only = next(r for r in report.rows if r.model == "gpt-4o-mini")
	prov_only = next(r for r in report.rows if r.model == "gpt-4o")

	assert gw_only.provider_requests == 0
	assert gw_only.pct_delta_requests is None  # provider=0 → undefined pct

	assert prov_only.gateway_requests == 0
	assert prov_only.delta_requests == -5


@pytest.mark.asyncio
async def test_reconcile_service_pct_zero_denominator():
	"""When provider value is 0, pct_delta must be None (no division by zero)."""
	svc = AnalyticsService()
	gw = [_make_gw_row("2026-03-01", "gpt-4o-mini", 10, 500, 200, "0.15")]
	records = [ProviderRecord(date="2026-03-01", model="gpt-4o-mini", requests=0, input_tokens=0, output_tokens=0, cost_usd=0.0)]

	report = await svc.reconcile_with_provider(db=FakeReconcileDB(gw), org_id=uuid4(), provider="openai", records=records)

	row = report.rows[0]
	assert row.pct_delta_requests is None
	assert row.pct_delta_input_tokens is None
	assert row.pct_delta_output_tokens is None
	assert row.pct_delta_cost_usd is None


@pytest.mark.asyncio
async def test_reconcile_service_duplicate_provider_rows_merged():
	"""Two provider rows with same (date, model) are summed before comparison."""
	svc = AnalyticsService()
	gw = [_make_gw_row("2026-03-01", "gpt-4o-mini", 200, 10000, 4000, "3.00")]
	records = [
		ProviderRecord(date="2026-03-01", model="gpt-4o-mini", requests=100, input_tokens=5000, output_tokens=2000, cost_usd=1.50),
		ProviderRecord(date="2026-03-01", model="gpt-4o-mini", requests=100, input_tokens=5000, output_tokens=2000, cost_usd=1.50),
	]

	report = await svc.reconcile_with_provider(db=FakeReconcileDB(gw), org_id=uuid4(), provider="openai", records=records)

	assert report.total_rows == 1
	assert report.mismatch_rows == 0
	assert report.rows[0].delta_requests == 0


@pytest.mark.asyncio
async def test_reconcile_service_multi_day_summary():
	"""Summary totals correctly aggregate across multiple date rows."""
	svc = AnalyticsService()
	gw = [
		_make_gw_row("2026-03-01", "gpt-4o-mini", 100, 5000, 2000, "1.50"),
		_make_gw_row("2026-03-02", "gpt-4o-mini", 120, 6000, 2400, "1.80"),
	]
	records = [
		ProviderRecord(date="2026-03-01", model="gpt-4o-mini", requests=100, input_tokens=5000, output_tokens=2000, cost_usd=1.50),
		ProviderRecord(date="2026-03-02", model="gpt-4o-mini", requests=100, input_tokens=5000, output_tokens=2000, cost_usd=1.50),
	]

	report = await svc.reconcile_with_provider(db=FakeReconcileDB(gw), org_id=uuid4(), provider="openai", records=records)

	assert report.total_rows == 2
	assert report.mismatch_rows == 1  # only day 2 mismatches
	assert report.summary.total_gateway_requests == 220
	assert report.summary.total_provider_requests == 200
	assert report.summary.total_delta_requests == 20


# ---------------------------------------------------------------------------
# Log detail endpoint tests
# ---------------------------------------------------------------------------


def test_log_detail_returns_full_record(client, monkeypatch):
	"""GET /analytics/logs/{id} returns RequestLogDetail with metadata."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")
	log_id = uuid4()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_log_detail(**kwargs):  # noqa: ANN003
		assert kwargs["org_id"] == org_id
		assert kwargs["log_id"] == log_id
		from datetime import UTC, datetime
		from app.schemas.logs import RequestLogDetail
		return RequestLogDetail(
			id=log_id,
			request_id=uuid4(),
			user_id=uuid4(),
			api_key_id=uuid4(),
			created_at=datetime.now(UTC),
			model="openai/gpt-4o-mini",
			provider="openai",
			status="success",
			status_code=200,
			prompt_tokens=100,
			completion_tokens=50,
			total_tokens=150,
			cost_usd=0.01,
			latency_ms=120,
			ttft_ms=40,
			error_message=None,
			policy_action="allow",
			policy_reason=None,
			policy_triggered_rules=[],
			request_metadata={"policy": {"action": "allow", "mode": "off"}},
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_log_detail", fake_get_log_detail)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		f"/api/v1/analytics/logs/{log_id}",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["id"] == str(log_id)
	assert data["model"] == "openai/gpt-4o-mini"
	assert data["status_code"] == 200
	assert data["request_metadata"]["policy"]["action"] == "allow"


def test_log_detail_returns_404_when_not_found(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_log_detail(**kwargs):  # noqa: ANN003
		return None

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_log_detail", fake_get_log_detail)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get(
		f"/api/v1/analytics/logs/{uuid4()}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404


def test_log_detail_requires_auth(client):
	response = client.get(f"/api/v1/analytics/logs/{uuid4()}")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# p50/p95/p99 latency percentile tests
# ---------------------------------------------------------------------------


def test_overview_response_includes_latency_percentiles(client, monkeypatch):
	"""Overview response contains p50/p95/p99 latency fields when data exists."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_overview(**kwargs):  # noqa: ANN003
		return AnalyticsResponse(
			overview=UsageOverview(
				period_days=30,
				total_requests=100,
				successful_requests=95,
				failed_requests=5,
				policy_blocked_requests=2,
				policy_flagged_requests=4,
				total_tokens=10000,
				total_cost_usd=5.00,
				avg_latency_ms=210.0,
				avg_ttft_ms=55.0,
				p50_latency_ms=180,
				p95_latency_ms=450,
				p99_latency_ms=780,
			),
			by_model=[],
			by_user=[],
			by_team=[],
			daily_trend=[],
			generated_at=datetime.now(UTC),
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_overview", fake_get_overview)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get("/api/v1/analytics/overview?period_days=30", headers={"Authorization": "Bearer test"})

	assert response.status_code == 200
	data = response.json()
	assert data["overview"]["p50_latency_ms"] == 180
	assert data["overview"]["p95_latency_ms"] == 450
	assert data["overview"]["p99_latency_ms"] == 780


def test_overview_response_latency_percentiles_null_when_no_data(client, monkeypatch):
	"""Overview response returns null for percentile fields when there are no requests."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role="admin")

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_overview(**kwargs):  # noqa: ANN003
		return AnalyticsResponse(
			overview=UsageOverview(
				period_days=30,
				total_requests=0,
				successful_requests=0,
				failed_requests=0,
				policy_blocked_requests=0,
				policy_flagged_requests=0,
				total_tokens=0,
				total_cost_usd=0.0,
				avg_latency_ms=0.0,
				avg_ttft_ms=0.0,
				p50_latency_ms=None,
				p95_latency_ms=None,
				p99_latency_ms=None,
			),
			by_model=[],
			by_user=[],
			by_team=[],
			daily_trend=[],
			generated_at=datetime.now(UTC),
		)

	monkeypatch.setattr(analytics_service_module.analytics_service, "get_overview", fake_get_overview)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get("/api/v1/analytics/overview?period_days=30", headers={"Authorization": "Bearer test"})

	assert response.status_code == 200
	data = response.json()
	assert data["overview"]["p50_latency_ms"] is None
	assert data["overview"]["p95_latency_ms"] is None
	assert data["overview"]["p99_latency_ms"] is None


@pytest.mark.asyncio
async def test_cost_by_team_aggregates_team_attributed_requests():
	"""_cost_by_team returns cost per team from request_logs with team_id in metadata."""
	team_id = uuid4()
	org_id = uuid4()
	rows_data = [
		{"team_id": team_id, "name": "Engineering", "requests": 15, "tokens": 2000, "cost_usd": Decimal("2.50")},
	]

	class TeamCostFakeDB:
		async def execute(self, stmt, params):
			class Mappings:
				def all(self):
					return rows_data

			class Result:
				def mappings(self):
					return Mappings()

			return Result()

	svc = AnalyticsService()
	result = await svc._cost_by_team(db=TeamCostFakeDB(), org_id=org_id, since=date(2026, 1, 1))

	assert len(result) == 1
	assert result[0].team_id == team_id
	assert result[0].name == "Engineering"
	assert result[0].requests == 15
	assert result[0].tokens == 2000
	assert result[0].cost_usd == 2.5


def test_usage_overview_schema_accepts_nullable_percentiles():
	"""UsageOverview Pydantic model accepts None for all three percentile fields."""
	overview = UsageOverview(
		period_days=7,
		total_requests=0,
		successful_requests=0,
		failed_requests=0,
		total_tokens=0,
		total_cost_usd=0.0,
		avg_latency_ms=0.0,
		avg_ttft_ms=0.0,
	)
	assert overview.p50_latency_ms is None
	assert overview.p95_latency_ms is None
	assert overview.p99_latency_ms is None

	overview_with_data = UsageOverview(
		period_days=7,
		total_requests=50,
		successful_requests=50,
		failed_requests=0,
		total_tokens=5000,
		total_cost_usd=2.5,
		avg_latency_ms=300.0,
		avg_ttft_ms=80.0,
		p50_latency_ms=250,
		p95_latency_ms=600,
		p99_latency_ms=950,
	)
	assert overview_with_data.p50_latency_ms == 250
	assert overview_with_data.p95_latency_ms == 600
	assert overview_with_data.p99_latency_ms == 950
