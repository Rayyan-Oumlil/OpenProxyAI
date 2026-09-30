"""Request-path sessions run as the RLS-subject app role; system sessions do not."""

import pytest
from pydantic import ValidationError
from sqlalchemy import event

from app import database
from app.config import Settings


class _RecordingCursor:
	def __init__(self, log: list[str]) -> None:
		self._log = log

	def execute(self, statement: str) -> None:
		self._log.append(statement)

	def close(self) -> None:
		pass


class _RecordingConnection:
	def __init__(self) -> None:
		self.statements: list[str] = []

	def cursor(self) -> _RecordingCursor:
		return _RecordingCursor(self.statements)


def test_new_request_connections_switch_to_app_role():
	conn = _RecordingConnection()
	database.set_app_role(conn, None)
	assert conn.statements == ['SET ROLE "app_user"']


def test_listener_is_registered_on_request_engine_only():
	assert event.contains(database.engine.sync_engine, "connect", database.set_app_role)
	assert not event.contains(database.system_engine.sync_engine, "connect", database.set_app_role)


def test_session_factories_bind_to_their_engines():
	assert database.AsyncSessionLocal.kw["bind"] is database.engine
	assert database.SystemSessionLocal.kw["bind"] is database.system_engine


@pytest.mark.parametrize("role", ["", "app user", 'app"; DROP TABLE users; --', "1app", "a" * 64])
def test_app_role_must_be_a_plain_identifier(role):
	with pytest.raises(ValidationError, match="DB_APP_ROLE"):
		Settings(DB_APP_ROLE=role)


def test_app_role_accepts_identifiers():
	assert Settings(DB_APP_ROLE="app_user_2").DB_APP_ROLE == "app_user_2"


class _RecordingSyncConnection:
	def __init__(self) -> None:
		self.calls: list[tuple[str, dict]] = []

	def execute(self, statement, params=None):
		self.calls.append((str(statement), params or {}))


class _FakeSyncSession:
	def __init__(self, info: dict) -> None:
		self.info = info


def test_org_is_reapplied_at_the_start_of_every_transaction():
	conn = _RecordingSyncConnection()
	database.reapply_org_on_begin(_FakeSyncSession({database.RLS_ORG_KEY: "org-a"}), None, conn)
	assert len(conn.calls) == 1
	statement, params = conn.calls[0]
	assert "set_config('app.current_org_id'" in statement and params == {"org_id": "org-a"}


def test_sessions_without_an_org_are_left_alone():
	conn = _RecordingSyncConnection()
	database.reapply_org_on_begin(_FakeSyncSession({}), None, conn)
	assert conn.calls == []


def test_reapply_listener_is_registered_for_request_sessions():
	sync_cls = database.AsyncSessionLocal.kw.get("sync_session_class", database.Session)
	assert event.contains(sync_cls, "after_begin", database.reapply_org_on_begin)


async def test_set_session_org_id_remembers_the_org_on_the_session():
	import uuid

	class _Session:
		def __init__(self) -> None:
			self.info: dict = {}

		async def execute(self, *args, **kwargs):  # noqa: ARG002
			return None

	s = _Session()
	org = uuid.uuid4()
	await database.set_session_org_id(s, org)
	assert s.info[database.RLS_ORG_KEY] == str(org)
	await database.set_session_org_id(s, None)
	assert database.RLS_ORG_KEY not in s.info
