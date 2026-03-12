"""Analytics endpoint tests — org-scoped overview and logs responses."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.schemas.analytics import AnalyticsResponse, CostByModel, CostByUser, DailyUsageTrend, UsageOverview
from app.schemas.logs import Page, RequestLogItem
from app.services import analytics_service as analytics_service_module


class FakeDB:
	async def commit(self):
		return None


def test_analytics_overview_route_success(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True)

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
	assert data["by_model"][0]["provider"] == "openai"


def test_analytics_logs_route_success(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_request_logs(**kwargs):  # noqa: ANN003
		assert kwargs["org_id"] == org_id
		assert kwargs["page"] == 1
		assert kwargs["page_size"] == 10
		assert kwargs["status"] == "success"
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
		"/api/v1/analytics/logs?page=1&page_size=10&status=success",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["total"] == 1
	assert data["items"][0]["status"] == "success"


def test_analytics_overview_requires_auth(client):
	response = client.get("/api/v1/analytics/overview")
	assert response.status_code == 401


def test_analytics_logs_requires_auth(client):
	response = client.get("/api/v1/analytics/logs")
	assert response.status_code == 401
