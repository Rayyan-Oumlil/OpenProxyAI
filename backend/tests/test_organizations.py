"""Organization settings route tests — get/update org, policy, webhooks."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.services import admin_audit_service as audit_module
from app.services.policy_service import PolicyConfig, policy_store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ScalarOneResult:
	def __init__(self, value):
		self._value = value

	def scalar_one(self):
		return self._value


class _AllResult:
	def __init__(self, items):
		self._items = items

	def all(self):
		return self._items


class FakeDB:
	def __init__(self, *, scalar_result=None, get_result=None, execute_scalar=0, scalars_items=None):
		self._scalar_result = scalar_result
		self._get_result = get_result
		self._execute_scalar = execute_scalar
		self._scalars_items = scalars_items or []
		self.committed = False
		self.added = []

	async def scalar(self, *args, **kwargs):
		return self._scalar_result

	async def scalars(self, *args, **kwargs):
		return _AllResult(self._scalars_items)

	async def execute(self, *args, **kwargs):
		return _ScalarOneResult(self._execute_scalar)

	async def get(self, model_cls, pk):
		return self._get_result

	async def commit(self):
		self.committed = True

	async def refresh(self, obj):
		pass

	def add(self, obj):
		self.added.append(obj)


class FakeRedis:
	"""Minimal stub for policy endpoints that take a redis dependency."""
	pass


def _make_org(org_id=None, *, plan="pro", settings=None, stripe_subscription_id=None):
	return SimpleNamespace(
		id=org_id or uuid4(),
		name="Acme Corp",
		slug="acme-corp",
		plan=plan,
		settings=settings or {},
		budget_monthly_usd=Decimal("500.00"),
		is_active=True,
		data_region="us-east-1",
		created_at=datetime.now(UTC),
		stripe_customer_id=None,
		stripe_subscription_id=stripe_subscription_id,
		stripe_subscription_status=None,
	)


def _make_user(org_id, *, role="admin"):
	return SimpleNamespace(
		id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True, role=role
	)


def _override_auth(user):
	async def dep():
		return user
	app.dependency_overrides[get_current_user_from_jwt] = dep


def _override_db(db_instance):
	async def dep():
		yield db_instance
	app.dependency_overrides[get_db] = dep


def _override_redis():
	app.dependency_overrides[get_redis] = lambda: FakeRedis()


def _noop_audit(monkeypatch):
	async def noop_log(*args, **kwargs):
		return SimpleNamespace(id=uuid4())

	monkeypatch.setattr(audit_module, "log_admin_action", noop_log)
	monkeypatch.setattr(audit_module, "serialize_org", lambda o: {})
	monkeypatch.setattr(audit_module, "serialize_webhook_config", lambda c: {})


# ---------------------------------------------------------------------------
# GET /api/v1/organizations/current — get current org
# ---------------------------------------------------------------------------


def test_get_current_org_success(client):
	org_id = uuid4()
	org = _make_org(org_id)
	user = _make_user(org_id)

	_override_auth(user)
	_override_db(FakeDB(scalar_result=org))

	response = client.get(
		"/api/v1/organizations/current",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["name"] == "Acme Corp"
	assert data["slug"] == "acme-corp"
	assert data["plan"] == "pro"
	assert data["is_active"] is True


def test_get_current_org_not_found(client):
	org_id = uuid4()
	user = _make_user(org_id)

	_override_auth(user)
	_override_db(FakeDB(scalar_result=None))

	response = client.get(
		"/api/v1/organizations/current",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404


def test_get_current_org_requires_auth(client):
	response = client.get("/api/v1/organizations/current")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/v1/organizations/current — update org (admin only)
# ---------------------------------------------------------------------------


def test_update_org_success(client, monkeypatch):
	org_id = uuid4()
	org = _make_org(org_id)
	user = _make_user(org_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(scalar_result=org))

	response = client.patch(
		"/api/v1/organizations/current",
		json={"name": "New Name"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	assert org.name == "New Name"


def test_update_org_settings_merge(client, monkeypatch):
	org_id = uuid4()
	org = _make_org(org_id, settings={"existing_key": "value"})
	user = _make_user(org_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(scalar_result=org))

	response = client.patch(
		"/api/v1/organizations/current",
		json={"settings": {"new_key": "new_value"}},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	assert org.settings["existing_key"] == "value"
	assert org.settings["new_key"] == "new_value"


def test_update_org_rejects_server_managed_stripe_metered_cache(client, monkeypatch):
	org_id = uuid4()
	org = _make_org(org_id, settings={})
	user = _make_user(org_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(scalar_result=org))

	response = client.patch(
		"/api/v1/organizations/current",
		json={"settings": {"stripe_metered_subscription_item_id": "si_evil"}},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 400
	assert "stripe_metered_subscription_item_id" in response.json()["detail"]


def test_update_org_forbidden_non_admin(client):
	org_id = uuid4()
	user = _make_user(org_id, role="developer")

	_override_auth(user)
	_override_db(FakeDB())

	response = client.patch(
		"/api/v1/organizations/current",
		json={"name": "Nope"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403
	assert response.json()["detail"] == "Forbidden"


def test_update_org_deactivation_rejected(client, monkeypatch):
	org_id = uuid4()
	org = _make_org(org_id)
	user = _make_user(org_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(scalar_result=org))

	response = client.patch(
		"/api/v1/organizations/current",
		json={"is_active": False},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 400
	assert "deactivation" in response.json()["detail"].lower()


def test_update_org_plan_change_conflict_with_stripe(client, monkeypatch):
	org_id = uuid4()
	org = _make_org(org_id, stripe_subscription_id="sub_abc123")
	user = _make_user(org_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(scalar_result=org))

	response = client.patch(
		"/api/v1/organizations/current",
		json={"plan": "enterprise"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 409
	assert "stripe" in response.json()["detail"].lower()


def test_update_org_requires_auth(client):
	response = client.patch(
		"/api/v1/organizations/current",
		json={"name": "x"},
	)
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/organizations/current/policy — get policy config
# ---------------------------------------------------------------------------


def test_get_policy_config_success(client, monkeypatch):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")

	config = PolicyConfig(
		enforcement_mode="enforce",
		allowed_models=["openai/gpt-4o-mini"],
		blocked_keywords=["secret"],
		pii_detection_enabled=True,
		pii_entities=["EMAIL"],
		model_rate_limits={},
		updated_at=datetime.now(UTC),
		prompt_injection_detection_enabled=False,
		response_guardrails_enabled=False,
		response_pii_redact=False,
	)

	async def fake_load(org_id_arg, db, redis):
		return config

	monkeypatch.setattr(policy_store, "load", fake_load)
	_override_auth(user)
	_override_db(FakeDB())
	_override_redis()

	response = client.get(
		"/api/v1/organizations/current/policy",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["enforcement_mode"] == "enforce"
	assert data["allowed_models"] == ["openai/gpt-4o-mini"]
	assert data["blocked_keywords"] == ["secret"]
	assert data["pii_detection_enabled"] is True


def test_get_policy_config_requires_auth(client):
	response = client.get("/api/v1/organizations/current/policy")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/v1/organizations/current/policy — update policy (admin only)
# ---------------------------------------------------------------------------


def test_update_policy_config_success(client, monkeypatch):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")

	current_config = PolicyConfig(
		enforcement_mode="off",
		updated_at=datetime.now(UTC),
	)

	async def fake_load(org_id_arg, db, redis):
		return current_config

	saved = {}

	async def fake_save(org_id_arg, new_config, db, redis):
		saved["config"] = new_config

	monkeypatch.setattr(policy_store, "load", fake_load)
	monkeypatch.setattr(policy_store, "save", fake_save)
	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB())
	_override_redis()

	response = client.patch(
		"/api/v1/organizations/current/policy",
		json={"enforcement_mode": "enforce", "blocked_keywords": ["badword"]},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["enforcement_mode"] == "enforce"
	assert data["blocked_keywords"] == ["badword"]
	assert "config" in saved


def test_update_policy_forbidden_non_admin(client, monkeypatch):
	org_id = uuid4()
	user = _make_user(org_id, role="developer")

	_override_auth(user)
	_override_db(FakeDB())
	_override_redis()

	response = client.patch(
		"/api/v1/organizations/current/policy",
		json={"enforcement_mode": "enforce"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_update_policy_requires_auth(client):
	response = client.patch(
		"/api/v1/organizations/current/policy",
		json={"enforcement_mode": "enforce"},
	)
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/organizations/current/webhooks — get webhook config
# ---------------------------------------------------------------------------


def test_get_webhook_config_success(client):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	org = _make_org(org_id, settings={
		"webhooks": {
			"url": "https://1.1.1.1/hook",
			"events": ["policy.violation"],
			"enabled": True,
		}
	})

	_override_auth(user)
	_override_db(FakeDB(get_result=org))

	response = client.get(
		"/api/v1/organizations/current/webhooks",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["url"] == "https://1.1.1.1/hook"
	assert data["events"] == ["policy.violation"]
	assert data["enabled"] is True


def test_get_webhook_config_defaults_when_empty(client):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	org = _make_org(org_id, settings={})

	_override_auth(user)
	_override_db(FakeDB(get_result=org))

	response = client.get(
		"/api/v1/organizations/current/webhooks",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["url"] == ""
	assert data["enabled"] is False


def test_get_webhook_config_forbidden_non_admin(client):
	org_id = uuid4()
	user = _make_user(org_id, role="developer")

	_override_auth(user)
	_override_db(FakeDB())

	response = client.get(
		"/api/v1/organizations/current/webhooks",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_get_webhook_config_requires_auth(client):
	response = client.get("/api/v1/organizations/current/webhooks")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/v1/organizations/current/webhooks — update webhook config
# ---------------------------------------------------------------------------


def test_update_webhook_config_success(client, monkeypatch):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	org = _make_org(org_id, settings={"webhooks": {"url": "", "enabled": False}})

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(get_result=org))

	response = client.patch(
		"/api/v1/organizations/current/webhooks",
		json={
			"url": "https://1.1.1.1/notify",
			"secret": "whsec_test",
			"events": ["policy.violation", "budget.alert"],
			"enabled": True,
		},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["url"] == "https://1.1.1.1/notify"
	assert data["enabled"] is True
	assert "secret" not in data
	assert org.settings["webhooks"]["secret"] == "whsec_test"


def test_update_webhook_config_forbidden_non_admin(client):
	org_id = uuid4()
	user = _make_user(org_id, role="viewer")

	_override_auth(user)
	_override_db(FakeDB())

	response = client.patch(
		"/api/v1/organizations/current/webhooks",
		json={"url": "https://x.com/hook", "enabled": True},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_update_webhook_config_requires_auth(client):
	response = client.patch(
		"/api/v1/organizations/current/webhooks",
		json={"url": "https://x.com/hook"},
	)
	assert response.status_code == 401


def test_update_webhook_config_invalid_url(client, monkeypatch):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	org = _make_org(org_id)

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(get_result=org))

	response = client.patch(
		"/api/v1/organizations/current/webhooks",
		json={"url": "ftp://bad.example.com", "enabled": True},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 422


def test_update_webhook_config_invalid_event(client, monkeypatch):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	org = _make_org(org_id)

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(get_result=org))

	response = client.patch(
		"/api/v1/organizations/current/webhooks",
		json={
			"url": "https://1.1.1.1/hook",
			"events": ["policy.violation", "unknown.event"],
			"enabled": True,
		},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 422


def test_update_webhook_org_not_found(client, monkeypatch):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(user)
	_override_db(FakeDB(get_result=None))

	response = client.patch(
		"/api/v1/organizations/current/webhooks",
		json={"url": "https://1.1.1.1/hook", "enabled": True},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/organizations/current/webhooks/deliveries
# ---------------------------------------------------------------------------


def _make_delivery(org_id, *, delivery_status="failed", event_type="budget.alert"):
	return SimpleNamespace(
		id=uuid4(),
		org_id=org_id,
		event_type=event_type,
		url="https://1.1.1.1/hook",
		status=delivery_status,
		http_status=500 if delivery_status == "failed" else 200,
		attempt_count=3 if delivery_status == "failed" else 1,
		last_attempted_at=datetime.now(UTC),
		created_at=datetime.now(UTC),
		payload={"event": event_type, "data": {}},
	)


def test_list_deliveries_success(client):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	deliveries = [_make_delivery(org_id) for _ in range(3)]

	_override_auth(user)
	_override_db(FakeDB(execute_scalar=3, scalars_items=deliveries))

	response = client.get(
		"/api/v1/organizations/current/webhooks/deliveries",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["total"] == 3
	assert len(data["items"]) == 3
	assert data["page"] == 1
	assert data["total_pages"] == 1


def test_list_deliveries_empty(client):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")

	_override_auth(user)
	_override_db(FakeDB(execute_scalar=0, scalars_items=[]))

	response = client.get(
		"/api/v1/organizations/current/webhooks/deliveries",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["total"] == 0
	assert len(data["items"]) == 0


def test_list_deliveries_with_status_filter(client):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	deliveries = [_make_delivery(org_id, delivery_status="failed")]

	_override_auth(user)
	_override_db(FakeDB(execute_scalar=1, scalars_items=deliveries))

	response = client.get(
		"/api/v1/organizations/current/webhooks/deliveries?status=failed",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["total"] == 1


def test_list_deliveries_pagination(client):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	deliveries = [_make_delivery(org_id)]

	_override_auth(user)
	_override_db(FakeDB(execute_scalar=25, scalars_items=deliveries))

	response = client.get(
		"/api/v1/organizations/current/webhooks/deliveries?page=2&page_size=10",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["total"] == 25
	assert data["page"] == 2
	assert data["page_size"] == 10
	assert data["total_pages"] == 3


def test_list_deliveries_forbidden_non_admin(client):
	org_id = uuid4()
	user = _make_user(org_id, role="developer")

	_override_auth(user)
	_override_db(FakeDB())

	response = client.get(
		"/api/v1/organizations/current/webhooks/deliveries",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_list_deliveries_requires_auth(client):
	response = client.get("/api/v1/organizations/current/webhooks/deliveries")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/organizations/current/webhooks/deliveries/{id}/retry
# ---------------------------------------------------------------------------


def test_retry_delivery_success(client, monkeypatch):
	from app.routes import organizations as org_module

	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	delivery = _make_delivery(org_id, delivery_status="failed")
	org = _make_org(org_id, settings={"webhooks": {"secret": "s3cret", "url": "https://1.1.1.1/hook", "enabled": True}})

	_override_auth(user)
	_override_db(FakeDB(scalar_result=delivery, get_result=org))

	async def fake_deliver(url, payload, secret):
		return "delivered", 200

	monkeypatch.setattr(org_module, "_deliver", fake_deliver)

	response = client.post(
		f"/api/v1/organizations/current/webhooks/deliveries/{delivery.id}/retry",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["status"] == "delivered"
	assert data["http_status"] == 200
	assert "payload" in data


def test_retry_delivery_already_delivered(client, monkeypatch):

	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	delivery = _make_delivery(org_id, delivery_status="delivered")

	_override_auth(user)
	_override_db(FakeDB(scalar_result=delivery))

	response = client.post(
		f"/api/v1/organizations/current/webhooks/deliveries/{delivery.id}/retry",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 409
	assert "already succeeded" in response.json()["detail"].lower()


def test_retry_delivery_not_found(client):
	org_id = uuid4()
	user = _make_user(org_id, role="admin")

	_override_auth(user)
	_override_db(FakeDB(scalar_result=None))

	response = client.post(
		f"/api/v1/organizations/current/webhooks/deliveries/{uuid4()}/retry",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404


def test_retry_delivery_forbidden_non_admin(client):
	org_id = uuid4()
	user = _make_user(org_id, role="developer")

	_override_auth(user)
	_override_db(FakeDB())

	response = client.post(
		f"/api/v1/organizations/current/webhooks/deliveries/{uuid4()}/retry",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_retry_delivery_unsafe_url_rejected(client, monkeypatch):
	from app.routes import organizations as org_module

	org_id = uuid4()
	user = _make_user(org_id, role="admin")
	delivery = _make_delivery(org_id, delivery_status="failed")
	org = _make_org(org_id, settings={"webhooks": {"secret": "s"}})

	_override_auth(user)
	_override_db(FakeDB(scalar_result=delivery, get_result=org))

	async def fake_deliver(url, payload, secret):
		return "failed", None

	monkeypatch.setattr(org_module, "_deliver", fake_deliver)

	response = client.post(
		f"/api/v1/organizations/current/webhooks/deliveries/{delivery.id}/retry",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 400
	assert "no longer considered safe" in response.json()["detail"].lower()


def test_retry_delivery_requires_auth(client):
	response = client.post(f"/api/v1/organizations/current/webhooks/deliveries/{uuid4()}/retry")
	assert response.status_code == 401
