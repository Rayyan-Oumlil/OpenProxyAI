"""Tool-call policy for the MCP gateway: allow/block patterns plus argument guardrails."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.services import policy_service as policy_service_module
from app.services.policy_service import PolicyConfig, policy_service


def _cfg(**kw) -> PolicyConfig:
	return PolicyConfig(**{"enforcement_mode": "enforce", "pii_detection_enabled": False, **kw})


def test_mcp_fields_round_trip_through_dict():
	cfg = _cfg(mcp_allowed_tools=["github__*"], mcp_blocked_tools=["*__delete_*"])
	again = PolicyConfig.from_dict(cfg.to_dict())
	assert again.mcp_allowed_tools == ["github__*"]
	assert again.mcp_blocked_tools == ["*__delete_*"]


def test_defaults_allow_every_tool():
	assert PolicyConfig.from_dict({}).mcp_allowed_tools == []
	assert policy_service.evaluate_tool_call("github__search", {}, _cfg()).allowed


def test_off_mode_skips_all_tool_checks():
	cfg = _cfg(enforcement_mode="off", mcp_allowed_tools=["jira__*"], blocked_keywords=["secret"])
	assert policy_service.evaluate_tool_call("github__search", {"q": "secret"}, cfg).allowed


def test_allowlist_blocks_unlisted_tools():
	cfg = _cfg(mcp_allowed_tools=["github__*"])
	assert policy_service.evaluate_tool_call("github__search", {}, cfg).allowed
	decision = policy_service.evaluate_tool_call("jira__create_issue", {}, cfg)
	assert not decision.allowed and decision.reason_code == "tool_not_allowed"


def test_blocklist_wins_over_allowlist():
	cfg = _cfg(mcp_allowed_tools=["github__*"], mcp_blocked_tools=["*__delete_*"])
	decision = policy_service.evaluate_tool_call("github__delete_repo", {}, cfg)
	assert not decision.allowed and decision.reason_code == "tool_blocked"


def test_blocked_keyword_in_arguments_is_caught():
	cfg = _cfg(blocked_keywords=["drop table"])
	decision = policy_service.evaluate_tool_call("postgres__query", {"sql": "DROP TABLE users"}, cfg)
	assert not decision.allowed and decision.reason_code == "blocked_keyword"


def test_pii_in_nested_arguments_is_caught():
	cfg = _cfg(pii_detection_enabled=True)
	decision = policy_service.evaluate_tool_call("crm__update", {"contact": {"ssn": "123-45-6789"}}, cfg)
	assert not decision.allowed and decision.reason_code == "pii_detected"


def test_log_only_reports_but_allows():
	cfg = _cfg(enforcement_mode="log_only", mcp_allowed_tools=["github__*"])
	decision = policy_service.evaluate_tool_call("jira__create_issue", {}, cfg)
	assert decision.allowed and decision.action == "log_only" and decision.reason_code == "tool_not_allowed"


def test_policy_api_accepts_and_returns_mcp_fields(client, monkeypatch):
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), email="a@t.com", role="admin", is_active=True)
	saved: list[PolicyConfig] = []

	class _DB:
		info: dict = {}

		def add(self, obj):
			pass

		async def commit(self):
			return None

	async def fake_user():
		return user

	async def fake_db():
		yield _DB()

	async def fake_redis():
		return None

	async def fake_load(org_id, db, redis):
		return _cfg(mcp_blocked_tools=["*__delete_*"])

	async def fake_save(org_id, config, db, redis):
		saved.append(config)

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	monkeypatch.setattr(policy_service_module.policy_store, "save", fake_save)
	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	app.dependency_overrides[get_db] = fake_db
	app.dependency_overrides[get_redis] = fake_redis

	response = client.patch(
		"/api/v1/organizations/current/policy",
		json={"mcp_allowed_tools": ["github__*"]},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200, response.text
	body = response.json()
	assert body["mcp_allowed_tools"] == ["github__*"]
	assert body["mcp_blocked_tools"] == ["*__delete_*"]
	assert saved[0].mcp_allowed_tools == ["github__*"]


@pytest.mark.parametrize("pattern", ["", "x" * 201])
def test_policy_api_rejects_empty_or_huge_patterns(client, monkeypatch, pattern):
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), email="a@t.com", role="admin", is_active=True)

	async def fake_user():
		return user

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	response = client.patch(
		"/api/v1/organizations/current/policy",
		json={"mcp_allowed_tools": [pattern]},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 422
