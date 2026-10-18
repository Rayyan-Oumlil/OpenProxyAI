"""Compliance templates API tests — apply-template and list templates."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4


from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.services import policy_service as policy_service_module
from app.services.compliance_templates import HEALTHCARE_HIPAA, FINANCE_PCI, GOVERNMENT_FEDRAMP
from app.services.policy_service import PolicyConfig, _POLICY_CACHE_KEY


class FakeDB:

	@property
	def info(self) -> dict:
		# Mirrors AsyncSession.info (set_session_org_id stores the org there).
		return self.__dict__.setdefault("_info", {})

	def __init__(self, org=None):
		self.added = []
		self._org = org

	async def scalar(self, query):  # noqa: ARG002
		return self._org

	async def commit(self):
		return None

	async def refresh(self, obj):  # noqa: ARG002
		return None

	def add(self, obj):
		self.added.append(obj)


class FakeRedis:
	def __init__(self) -> None:
		self._store: dict[str, str] = {}
		self.delete = AsyncMock(return_value=1)

	async def get(self, key: str) -> str | None:
		return self._store.get(key)

	async def setex(self, key: str, ttl: int, value: str) -> bool:  # noqa: ARG002
		self._store[key] = value
		return True


def _org(org_id, plan="starter", settings=None):
	return SimpleNamespace(
		id=org_id,
		name="TestOrg",
		slug="testorg",
		plan=plan,
		settings=settings or {},
		budget_monthly_usd=None,
		is_active=True,
		data_region="us",
	)


# ── Apply healthcare template ──────────────────────────────────────────────────


def test_apply_healthcare_template(client, monkeypatch):
	org_id = uuid4()
	org = _org(org_id)
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)
	fake_redis = FakeRedis()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(org)

	async def fake_get_redis():
		return fake_redis

	async def fake_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig(
			enforcement_mode="off",
			allowed_models=[],
			blocked_keywords=[],
			pii_detection_enabled=False,
			pii_entities=[],
			model_rate_limits={},
		)

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "healthcare_hipaa"},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["enforcement_mode"] == "enforce"
	assert data["pii_detection_enabled"] is True
	assert data["prompt_injection_detection_enabled"] is True
	assert data["response_guardrails_enabled"] is True
	assert data["response_pii_redact"] is True
	assert set(data["blocked_keywords"]) == set(HEALTHCARE_HIPAA.blocked_keywords)
	assert set(data["pii_entities"]) == set(HEALTHCARE_HIPAA.pii_entities)
	assert org.settings["policy"]["metadata"]["template"] == "healthcare_hipaa"
	assert org.settings["policy"]["metadata"]["audit_retention_days"] == 2555


def test_apply_finance_template(client, monkeypatch):
	org_id = uuid4()
	org = _org(org_id)
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)
	fake_redis = FakeRedis()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(org)

	async def fake_get_redis():
		return fake_redis

	async def fake_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig()

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "finance_pci"},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["enforcement_mode"] == "enforce"
	assert set(data["blocked_keywords"]) == set(FINANCE_PCI.blocked_keywords)
	assert set(data["pii_entities"]) == set(FINANCE_PCI.pii_entities)
	assert org.settings["policy"]["metadata"]["template"] == "finance_pci"
	assert org.settings["policy"]["metadata"]["audit_retention_days"] == 365


def test_apply_government_template(client, monkeypatch):
	org_id = uuid4()
	org = _org(org_id)
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)
	fake_redis = FakeRedis()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(org)

	async def fake_get_redis():
		return fake_redis

	async def fake_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig()

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "government_fedramp"},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["enforcement_mode"] == "enforce"
	assert set(data["blocked_keywords"]) == set(GOVERNMENT_FEDRAMP.blocked_keywords)
	assert set(data["pii_entities"]) == set(GOVERNMENT_FEDRAMP.pii_entities)
	assert org.settings["policy"]["metadata"]["template"] == "government_fedramp"
	assert org.settings["policy"]["metadata"]["audit_retention_days"] == 1095


# ── Merge semantics: preserve allowed_models and model_rate_limits ──────────────


def test_apply_template_preserves_allowed_models(client, monkeypatch):
	org_id = uuid4()
	org = _org(org_id)
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)
	fake_redis = FakeRedis()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(org)

	async def fake_get_redis():
		return fake_redis

	async def fake_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig(
			allowed_models=["openai/gpt-4o", "anthropic/claude-3"],
			model_rate_limits={"openai/gpt-4o": {"rpm": 100, "tpm": 50000}},
		)

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "healthcare_hipaa"},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["allowed_models"] == ["openai/gpt-4o", "anthropic/claude-3"]
	assert data["model_rate_limits"] == {"openai/gpt-4o": {"rpm": 100, "tpm": 50000}}


def test_apply_template_preserves_model_rate_limits(client, monkeypatch):
	org_id = uuid4()
	org = _org(org_id)
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)
	fake_redis = FakeRedis()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(org)

	async def fake_get_redis():
		return fake_redis

	async def fake_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig(
			allowed_models=[],
			model_rate_limits={"openai/gpt-4o": {"rpm": 60}, "anthropic/claude-3": {"tpm": 100000}},
		)

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "finance_pci"},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["model_rate_limits"] == {"openai/gpt-4o": {"rpm": 60}, "anthropic/claude-3": {"tpm": 100000}}


# ── Validation and auth ──────────────────────────────────────────────────────


def test_apply_template_unknown_returns_400(client, monkeypatch):
	org_id = uuid4()
	org = _org(org_id)
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(org)

	async def fake_get_redis():
		return FakeRedis()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "unknown_template"},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 400
	assert "Unknown template" in response.json().get("detail", "")


def test_apply_template_non_admin_403(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="user@test.com", role="member", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(_org(org_id))

	async def fake_get_redis():
		return FakeRedis()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "healthcare_hipaa"},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 403


# ── Redis cache and audit log ──────────────────────────────────────────────────


def test_apply_template_clears_redis_cache(client, monkeypatch):
	org_id = uuid4()
	org = _org(org_id)
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)
	fake_redis = FakeRedis()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(org)

	async def fake_get_redis():
		return fake_redis

	async def fake_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig()

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "healthcare_hipaa"},
		headers={"Authorization": "Bearer test"},
	)

	expected_key = _POLICY_CACHE_KEY.format(org_id=org_id)
	fake_redis.delete.assert_awaited_once_with(expected_key)


def test_apply_template_creates_audit_log(client, monkeypatch):
	org_id = uuid4()
	org = _org(org_id)
	fake_db = FakeDB(org)
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)
	fake_redis = FakeRedis()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield fake_db

	async def fake_get_redis():
		return fake_redis

	async def fake_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig()

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	client.post(
		"/api/v1/organizations/current/policy/apply-template",
		json={"template": "healthcare_hipaa"},
		headers={"Authorization": "Bearer test"},
	)

	audit_entries = [a for a in fake_db.added if hasattr(a, "action") and a.action == "apply_compliance_template"]
	assert len(audit_entries) == 1
	assert audit_entries[0].after == {"template": "healthcare_hipaa"}


# ── List templates ────────────────────────────────────────────────────────────


def test_list_templates_returns_all_three(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)

	async def fake_current_user_dep():
		return user

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep

	response = client.get(
		"/api/v1/organizations/current/policy/templates",
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert len(data) == 3
	names = {t["name"] for t in data}
	assert names == {"healthcare_hipaa", "finance_pci", "government_fedramp"}
	for t in data:
		assert "description" in t
		assert "configures" in t
		assert isinstance(t["configures"], list)
		assert len(t["configures"]) > 0
