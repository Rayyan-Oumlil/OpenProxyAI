"""Opt-in payload capture (Phase 3, slice 2): what may be stored of a request, and what never is."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.schemas.chat import Message
from app.services import payload_capture as pc
from app.services.classification_service import Classification
from app.services.llm_service import LLMService
from app.services.policy_service import PolicyConfig


# ── whether to capture ───────────────────────────────────────────────────────


def decide(rate, data_class="internal", ceiling="internal", draw=0.0):
	return pc.should_capture(sample_rate=rate, data_class=data_class, ceiling=ceiling, draw=draw)


def test_nothing_is_captured_at_rate_zero_whatever_the_draw():
	assert [decide(0.0, draw=d) for d in (0.0, 0.5, 0.999)] == [False, False, False]


def test_everything_below_the_ceiling_is_captured_at_rate_one():
	assert [decide(1.0, draw=d) for d in (0.0, 0.5, 0.999)] == [True, True, True]


def test_the_rate_is_the_chance_that_a_request_is_kept():
	assert decide(0.25, draw=0.24) is True
	assert decide(0.25, draw=0.25) is False


@pytest.mark.parametrize("data_class,expected", [("public", True), ("internal", True), ("confidential", False), ("secret", False)])
def test_a_request_above_the_data_class_ceiling_is_never_stored(data_class, expected):
	assert decide(1.0, data_class=data_class, ceiling="internal") is expected


def test_the_ceiling_can_be_raised_by_the_operator():
	assert decide(1.0, data_class="confidential", ceiling="confidential") is True
	assert decide(1.0, data_class="secret", ceiling="confidential") is False


@pytest.mark.parametrize("rate", [-1, 1.5, float("nan"), None, "0.5"])
def test_a_nonsense_rate_means_off(rate):
	assert decide(rate) is False


# ── what is stored ───────────────────────────────────────────────────────────


def test_pii_is_redacted_from_messages_and_the_output_and_the_flag_says_so():
	messages, redacted = pc.prepare_messages(
		[Message(role="user", content="Email jane.doe@example.com, SSN 123-45-6789"), Message(role="assistant", content="Sure.")]
	)
	assert redacted is True
	assert "jane.doe@example.com" not in messages[0]["content"] and "123-45-6789" not in messages[0]["content"]
	assert messages[1] == {"role": "assistant", "content": "Sure."}
	output, out_redacted = pc.prepare_output("Sent to jane.doe@example.com")
	assert out_redacted is True and "jane.doe@example.com" not in output


def test_text_without_pii_is_stored_exactly_and_not_flagged():
	messages, redacted = pc.prepare_messages([Message(role="user", content="Summarise Q3.")])
	assert (messages, redacted) == ([{"role": "user", "content": "Summarise Q3."}], False)
	assert pc.prepare_output("Revenue grew.") == ("Revenue grew.", False)


def test_list_content_keeps_text_parts_redacted_and_drops_everything_else():
	message = Message(
		role="user",
		content=[
			{"type": "text", "text": "mail me at jane.doe@example.com"},
			{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
		],
	)
	[stored], redacted = pc.prepare_messages([message])
	assert redacted is True
	assert stored["content"] == [{"type": "text", "text": "mail me at [REDACTED]"}, {"type": "omitted", "was": "image_url"}]


def test_only_role_and_content_are_kept_never_tool_calls_or_other_extras():
	message = Message(role="assistant", content=None, tool_calls=[{"id": "1", "function": {"arguments": "{\"ssn\": \"123-45-6789\"}"}}])
	[stored], _ = pc.prepare_messages([message])
	assert stored == {"role": "assistant", "content": None}


def test_an_oversized_field_is_cut_and_marked():
	text, _ = pc.prepare_output("x" * (pc.MAX_FIELD_CHARS + 500))
	assert len(text) <= pc.MAX_FIELD_CHARS + len(pc.TRUNCATION_MARK) and text.endswith(pc.TRUNCATION_MARK)


# ── storing it ───────────────────────────────────────────────────────────────


class FakeSession:
	"""Records the statements that touch a table; ignores the set_config calls that scope a session to an org."""

	def __init__(self, plan="free", fail=False, org_ids=()):
		self.org = SimpleNamespace(plan=plan)
		self.fail = fail
		self.org_ids = list(org_ids)
		self.statements = []
		self.commits = 0
		self.info = {}

	async def get(self, model, key):
		return self.org

	async def scalars(self, stmt):
		return iter(self.org_ids)

	async def execute(self, stmt, params=None):
		if self.fail:
			raise RuntimeError("database is down")
		if getattr(stmt, "table", None) is not None:
			self.statements.append(stmt)
		return SimpleNamespace(rowcount=3)

	async def commit(self):
		self.commits += 1


@pytest.fixture
def session(monkeypatch):
	holder = {"session": FakeSession()}

	@asynccontextmanager
	async def scoped(org_id):
		holder["org_id"] = org_id
		yield holder["session"]

	monkeypatch.setattr(pc, "org_scoped_session", scoped)
	return holder


def params(statement):
	return statement.compile(dialect=postgresql.dialect()).params


async def test_a_captured_payload_is_stored_under_the_org_with_an_expiry_from_the_plans_retention(session):
	org_id, request_id = uuid.uuid4(), uuid.uuid4()
	now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

	stored = await pc.capture_payload(org_id, request_id, [Message(role="user", content="hi jane.doe@example.com")], "hello", now=now)

	assert stored is True and session["org_id"] == org_id and session["session"].commits == 1
	row = params(session["session"].statements[0])
	assert row["org_id"] == org_id and row["request_id"] == request_id
	assert row["redacted"] is True and "jane.doe@example.com" not in str(row["messages"])
	assert row["expires_at"] == now + timedelta(days=7)  # the free plan keeps audit data 7 days


async def test_the_expiry_follows_the_plan(session):
	session["session"] = FakeSession(plan="enterprise")
	now = datetime(2026, 11, 9, tzinfo=UTC)
	await pc.capture_payload(uuid.uuid4(), uuid.uuid4(), [Message(role="user", content="hi")], "ok", now=now)
	assert params(session["session"].statements[0])["expires_at"] == now + timedelta(days=365)


async def test_a_failure_to_store_never_propagates(session):
	session["session"] = FakeSession(fail=True)
	assert await pc.capture_payload(uuid.uuid4(), uuid.uuid4(), [Message(role="user", content="hi")], "ok") is False


async def test_the_purge_deletes_expired_rows_one_org_at_a_time_and_reports_the_total(monkeypatch):
	fake = FakeSession(org_ids=[uuid.uuid4(), uuid.uuid4()])

	@asynccontextmanager
	async def unscoped():
		yield fake

	monkeypatch.setattr(pc, "AsyncSessionLocal", unscoped)
	assert await pc.purge_expired_payloads() == 6  # 3 rows from each of two orgs
	assert fake.commits == 1 and len(fake.statements) == 2
	sql = str(fake.statements[0].compile(dialect=postgresql.dialect()))
	assert sql.startswith("DELETE FROM request_payloads") and "expires_at" in sql and "org_id" in sql


# ── the hook in the request pipeline ─────────────────────────────────────────


def ctx(rate, data_class="internal"):
	return SimpleNamespace(
		policy_config=PolicyConfig(payload_capture_sample_rate=rate),
		classification=Classification(data_class, "default", ()),
		background_tasks=MagicMock(),
		request_id=uuid.uuid4(),
		user=SimpleNamespace(org_id=uuid.uuid4()),
		request=SimpleNamespace(messages=[Message(role="user", content="hi")]),
	)


def test_a_request_is_handed_to_the_capture_task_when_the_org_opted_in():
	c = ctx(1.0)
	LLMService._schedule_capture(c, "the answer")
	[call] = c.background_tasks.add_task.call_args_list
	assert call.args[0] is pc.capture_payload and call.args[1:3] == (c.user.org_id, c.request_id) and call.args[4] == "the answer"


def test_nothing_is_scheduled_when_the_org_has_not_opted_in():
	c = ctx(0.0)
	LLMService._schedule_capture(c, "the answer")
	assert not c.background_tasks.add_task.called


def test_a_confidential_request_is_not_scheduled_even_at_rate_one():
	c = ctx(1.0, data_class="confidential")
	LLMService._schedule_capture(c, "the answer")
	assert not c.background_tasks.add_task.called


def test_an_empty_answer_is_not_stored():
	c = ctx(1.0)
	LLMService._schedule_capture(c, "")
	assert not c.background_tasks.add_task.called


# ── the setting ──────────────────────────────────────────────────────────────


def test_the_default_is_off_and_it_survives_a_save_and_load():
	assert PolicyConfig().payload_capture_sample_rate == 0.0
	config = PolicyConfig(payload_capture_sample_rate=0.25)
	assert PolicyConfig.from_dict(config.to_dict()).payload_capture_sample_rate == 0.25


@pytest.mark.parametrize("stored", [None, "x", -1, 2, float("nan")])
def test_a_corrupt_stored_value_loads_as_off(stored):
	assert PolicyConfig.from_dict({"payload_capture_sample_rate": stored}).payload_capture_sample_rate == 0.0


# ── a background job runs in a bare process ──────────────────────────────────


def test_importing_the_models_package_alone_is_enough_to_configure_every_mapper():
	"""A scheduled job or script that imports only app.models must not fail on a class nobody registered.

	The first version of the purge job returned 0 in a standalone process because PromptTemplate (a relationship of
	Organization) was never imported; the app process hid it because main.py imports everything.
	"""
	import subprocess
	import sys
	from pathlib import Path

	result = subprocess.run(
		[sys.executable, "-c", "import app.models; from sqlalchemy.orm import configure_mappers; configure_mappers()"],
		cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True,
	)
	assert result.returncode == 0, result.stderr[-600:]
