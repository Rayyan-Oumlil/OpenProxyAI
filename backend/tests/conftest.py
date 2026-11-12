"""Test fixtures — test DB, test client, test API key, test user."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app


class FakeRedis:
	"""Small in-memory Redis substitute for auth tests."""

	def __init__(self) -> None:
		self._store: dict[str, str] = {}
		self._counter: dict[str, int] = {}
		self._zsets: dict[str, dict[str, float]] = {}
		self._hashes: dict[str, dict[str, str]] = {}

	class _Pipeline:
		def __init__(self, redis: "FakeRedis") -> None:
			self._redis = redis
			self._ops: list[tuple[str, tuple, dict]] = []

		def incr(self, *args, **kwargs):
			self._ops.append(("incr", args, kwargs))
			return self

		def zremrangebyscore(self, *args, **kwargs):
			self._ops.append(("zremrangebyscore", args, kwargs))
			return self

		def zcard(self, *args, **kwargs):
			self._ops.append(("zcard", args, kwargs))
			return self

		def zrange(self, *args, **kwargs):
			self._ops.append(("zrange", args, kwargs))
			return self

		def get(self, *args, **kwargs):
			self._ops.append(("get", args, kwargs))
			return self

		def zadd(self, *args, **kwargs):
			self._ops.append(("zadd", args, kwargs))
			return self

		def expire(self, *args, **kwargs):
			self._ops.append(("expire", args, kwargs))
			return self

		def incrby(self, *args, **kwargs):
			self._ops.append(("incrby", args, kwargs))
			return self

		async def execute(self):
			results = []
			for method, args, kwargs in self._ops:
				fn = getattr(self._redis, method)
				results.append(await fn(*args, **kwargs))
			self._ops.clear()
			return results

	async def incr(self, key: str) -> int:
		value = self._counter.get(key, 0) + 1
		self._counter[key] = value
		return value

	async def decr(self, key: str) -> int:
		value = self._counter.get(key, 0) - 1
		self._counter[key] = value
		return value

	async def expire(self, key: str, seconds: int) -> bool:  # noqa: ARG002
		return True

	async def get(self, key: str) -> str | None:
		if key in self._store:
			return self._store[key]
		if key in self._counter:
			return str(self._counter[key])
		return None

	async def incrby(self, key: str, amount: int) -> int:
		value = self._counter.get(key, 0) + amount
		self._counter[key] = value
		return value

	async def incrbyfloat(self, key: str, amount: float) -> float:
		current = float(self._store.get(key, "0"))
		current += amount
		self._store[key] = str(current)
		return current

	async def zadd(self, key: str, mapping: dict[str, float]) -> int:
		zset = self._zsets.setdefault(key, {})
		added = 0
		for member, score in mapping.items():
			if member not in zset:
				added += 1
			zset[member] = float(score)
		return added

	async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
		zset = self._zsets.get(key, {})
		to_remove = [member for member, score in zset.items() if min_score <= score <= max_score]
		for member in to_remove:
			del zset[member]
		return len(to_remove)

	async def zcard(self, key: str) -> int:
		return len(self._zsets.get(key, {}))

	async def zrange(self, key: str, start: int, stop: int, withscores: bool = False):
		items = sorted(self._zsets.get(key, {}).items(), key=lambda item: item[1])
		if stop == -1:
			slice_items = items[start:]
		else:
			slice_items = items[start : stop + 1]
		if withscores:
			return [(member, score) for member, score in slice_items]
		return [member for member, _ in slice_items]

	async def hset(self, key: str, mapping: dict[str, str] | None = None, **fields: str) -> int:
		self._hashes.setdefault(key, {}).update({**(mapping or {}), **fields})
		return len(mapping or {}) + len(fields)

	async def hgetall(self, key: str) -> dict[str, str]:
		return dict(self._hashes.get(key, {}))

	async def exists(self, key: str) -> int:
		return 1 if key in self._store else 0

	async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:  # noqa: ARG002
		if nx and key in self._store:
			return False
		self._store[key] = value
		return True

	async def setex(self, key: str, ttl: int, value: str) -> bool:  # noqa: ARG002
		self._store[key] = value
		return True

	async def delete(self, *keys: str) -> int:
		deleted = 0
		for key in keys:
			removed = False
			if key in self._store:
				del self._store[key]
				removed = True
			if key in self._counter:
				del self._counter[key]
				removed = True
			if removed:
				deleted += 1
		return deleted

	def pipeline(self, transaction: bool = True):  # noqa: ARG002
		return self._Pipeline(self)


class FakeDB:
	"""Minimal AsyncSession substitute for LLM service tests (execute, scalar, commit)."""

	@property
	def info(self) -> dict:
		# Mirrors AsyncSession.info (set_session_org_id stores the org there).
		return self.__dict__.setdefault("_info", {})


	async def execute(self, *args, **kwargs):
		return None

	async def scalar(self, *args, **kwargs):
		return None

	async def commit(self):
		return None


@pytest.fixture
def fake_db() -> FakeDB:
	return FakeDB()


@pytest.fixture
def fake_redis() -> FakeRedis:
	return FakeRedis()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
	with TestClient(app) as test_client:
		yield test_client


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
	app.dependency_overrides.clear()
	yield
	app.dependency_overrides.clear()


@pytest.fixture
async def tenants():
	import uuid
	from types import SimpleNamespace

	from sqlalchemy import text

	from app.database import AsyncSessionLocal, SystemSessionLocal
	from app.models.organization import Organization
	from app.models.user import User
	from app.utils.crypto import hash_password

	"""Two orgs; org A has an admin user and a server row. Cleaned up through org deletion (cascade)."""
	async with AsyncSessionLocal() as session:
		org_a = Organization(name="Pin A", slug=f"pin-a-{uuid.uuid4().hex[:8]}")
		org_b = Organization(name="Pin B", slug=f"pin-b-{uuid.uuid4().hex[:8]}")
		session.add_all([org_a, org_b])
		await session.flush()
		user = User(org_id=org_a.id, email=f"pin-{uuid.uuid4().hex[:8]}@test.local",
		            password_hash=hash_password("TestPass1!"), role="admin", is_active=True)
		session.add(user)
		await session.commit()
		ids = SimpleNamespace(a=org_a.id, b=org_b.id, user_a=SimpleNamespace(id=user.id, org_id=org_a.id, email=user.email, role="admin"))
	yield ids
	async with SystemSessionLocal() as session:
		await session.execute(text("DELETE FROM organizations WHERE id IN (:a, :b)"), {"a": ids.a, "b": ids.b})
		await session.commit()
