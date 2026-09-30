"""Every writer scopes its session to the row's org; only cross-org jobs use the system session.

These tests pin *which session and in which order*; the Postgres semantics themselves are
covered by tests/test_rls_isolation.py (integration, runs in CI against real Postgres).
"""

import json
import uuid
from decimal import Decimal

import pytest

from app import database
from app.services import (
	adaptive_sampling_service,
	audit_logger,
	cache_service,
	cost_tracker,
	key_rotation_scheduler,
	provider_health_service,
	spend_batch_service,
)

ORG_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ORG_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class _Empty:
	def all(self):
		return []

	def mappings(self):
		return self


class RecordingSession:
	"""Records set_config / add / flush / commit in order."""

	def __init__(self, log: list, name: str = "app") -> None:
		self.log = log
		self.name = name

	async def __aenter__(self):
		self.log.append(("open", self.name))
		return self

	async def __aexit__(self, *exc):
		return False

	async def execute(self, statement, params=None):
		if "set_config" in str(statement):
			self.log.append(("org", (params or {}).get("org_id")))
		else:
			self.log.append(("query", self.name))
		return _Empty()

	async def scalars(self, *args, **kwargs):  # noqa: ARG002
		self.log.append(("query", self.name))
		return _Empty()

	async def get(self, *args, **kwargs):  # noqa: ARG002
		return None

	def add(self, obj):
		self.log.append(("add", str(obj.org_id)))

	async def flush(self):
		self.log.append(("flush",))

	async def commit(self):
		self.log.append(("commit",))


@pytest.fixture
def log(monkeypatch) -> list:
	entries: list = []
	monkeypatch.setattr(database, "AsyncSessionLocal", lambda: RecordingSession(entries, "app"))
	return entries


def _assert_org_set_before_add(entries: list, org: uuid.UUID) -> None:
	org_idx = entries.index(("org", str(org)))
	add_idx = entries.index(("add", str(org)))
	assert org_idx < add_idx, entries


async def test_org_scoped_session_sets_org_before_yielding(log):
	async with database.org_scoped_session(ORG_A):
		log.append(("body",))
	assert log[:3] == [("open", "app"), ("org", str(ORG_A)), ("body",)]


async def test_org_scoped_session_rejects_non_uuid(log):  # noqa: ARG001
	with pytest.raises(TypeError):
		async with database.org_scoped_session(str(ORG_A)):  # type: ignore[arg-type]
			pass


async def test_request_log_insert_is_org_scoped(log, fake_redis, monkeypatch):
	monkeypatch.setattr(audit_logger.settings, "BATCH_SPEND_ENABLED", False)
	await audit_logger.log_request(
		redis=fake_redis,
		request_id=uuid.uuid4(),
		org_id=ORG_A,
		user_id=uuid.uuid4(),
		api_key_id=None,
		model="gpt-4o",
		provider="openai",
		prompt_tokens=1,
		completion_tokens=1,
		cost_usd=Decimal("0.001"),
		latency_ms=10,
		ttft_ms=None,
		status_code=200,
	)
	_assert_org_set_before_add(log, ORG_A)


async def test_policy_webhook_and_anomaly_sessions_are_org_scoped(log, fake_redis):
	await audit_logger._fire_policy_webhook(ORG_A, uuid.uuid4(), {}, "gpt-4o", uuid.uuid4())
	await audit_logger._fire_anomaly_check(fake_redis, ORG_B, uuid.uuid4())
	assert ("org", str(ORG_A)) in log and ("org", str(ORG_B)) in log


async def test_budget_webhook_session_is_org_scoped(log):
	await cost_tracker._fire_budget_webhook(str(ORG_A), 90.0, 100.0)
	assert log[:2] == [("open", "app"), ("org", str(ORG_A))]


async def test_semantic_cache_insert_is_org_scoped(log, monkeypatch):
	class _Emb:
		data = [type("D", (), {"embedding": [0.1, 0.2]})()]

	async def fake_embed(*args, **kwargs):  # noqa: ARG001
		return _Emb()

	monkeypatch.setattr(cache_service, "_embed_for_cache", fake_embed, raising=False)
	monkeypatch.setattr("litellm.aembedding", fake_embed)
	await cache_service._set_l3_semantic(ORG_A, "gpt-4o", [{"role": "user", "content": "hi"}], {"ok": True}, 3, 60)
	_assert_org_set_before_add(log, ORG_A)


class _ListRedis:
	def __init__(self, items: list[str]) -> None:
		self.items = items

	async def lpop(self, key):  # noqa: ARG002
		return self.items.pop(0) if self.items else None

	async def rpush(self, key, value):  # noqa: ARG002
		self.items.append(value)


def _serialized(org: uuid.UUID) -> str:
	return spend_batch_service._serialize_log_entry(
		uuid.uuid4(), org, uuid.uuid4(), None, "gpt-4o", "openai", 1, 1, 2,
		Decimal("0.001"), 10, None, 200, None, {},
	)


async def test_batch_flush_scopes_each_org_group(log, monkeypatch):
	monkeypatch.setattr(spend_batch_service.settings, "BATCH_SPEND_ENABLED", True)
	redis = _ListRedis([_serialized(ORG_A), _serialized(ORG_B), _serialized(ORG_A)])
	flushed = await spend_batch_service.flush_request_logs_batch(redis)
	assert flushed == 3
	events = [e for e in log if e[0] in ("org", "add", "flush", "commit")]
	assert events == [
		("org", str(ORG_A)), ("add", str(ORG_A)), ("add", str(ORG_A)), ("flush",),
		("org", str(ORG_B)), ("add", str(ORG_B)), ("flush",),
		("commit",),
	]
	assert redis.items == []


@pytest.fixture
def system_log(monkeypatch, log) -> list:
	monkeypatch.setattr(database, "SystemSessionLocal", lambda: RecordingSession(log, "system"))
	for module in (key_rotation_scheduler, provider_health_service, adaptive_sampling_service):
		monkeypatch.setattr(module, "SystemSessionLocal", lambda: RecordingSession(log, "system"), raising=False)
	return log


async def test_key_rotation_lists_keys_with_system_session(system_log, monkeypatch):
	monkeypatch.setattr(key_rotation_scheduler.settings, "KEY_ROTATION_SCHEDULER_ENABLED", True)
	await key_rotation_scheduler.run_key_rotation()
	assert ("query", "system") in system_log and ("query", "app") not in system_log


async def test_health_check_lists_keys_with_system_session(system_log, monkeypatch):
	monkeypatch.setattr(provider_health_service.settings, "PROVIDER_HEALTH_CHECK_ENABLED", True)
	await provider_health_service.run_provider_health_check()
	assert ("query", "system") in system_log and ("query", "app") not in system_log


async def test_adaptive_sampling_reads_logs_with_system_session(system_log, monkeypatch, fake_redis):
	monkeypatch.setattr(adaptive_sampling_service.settings, "ADAPTIVE_LB_ENABLED", True)

	class _Closable:
		def pipeline(self):
			return fake_redis.pipeline()

		async def aclose(self):
			return None

	monkeypatch.setattr(adaptive_sampling_service.aioredis, "from_url", lambda *a, **k: _Closable())
	await adaptive_sampling_service.run_adaptive_sampling_job()
	assert ("query", "system") in system_log and ("query", "app") not in system_log


def test_serialized_fixture_round_trips():
	entry = spend_batch_service._deserialize_log_entry(_serialized(ORG_A))
	assert str(entry["org_id"]) == str(ORG_A)
	assert json.loads(_serialized(ORG_B))
