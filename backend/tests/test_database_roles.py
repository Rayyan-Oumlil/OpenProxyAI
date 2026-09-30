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
