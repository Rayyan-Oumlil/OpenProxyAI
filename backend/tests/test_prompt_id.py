"""Tests for prompt_id resolution on the proxy — schema validation and template resolution."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatCompletionRequest, _substitute_variables


# ── _substitute_variables ────────────────────────────────────────────────────


def test_substitute_variables_single():
	assert _substitute_variables("Hello {{name}}", {"name": "World"}) == "Hello World"


def test_substitute_variables_multiple():
	tpl = "{{greeting}}, {{name}}!"
	assert _substitute_variables(tpl, {"greeting": "Hi", "name": "Alice"}) == "Hi, Alice!"


def test_substitute_variables_missing_key_becomes_empty():
	assert _substitute_variables("Hello {{name}}", {}) == "Hello "


def test_substitute_variables_no_placeholders():
	assert _substitute_variables("plain text", {"x": "y"}) == "plain text"


# ── ChatCompletionRequest schema ────────────────────────────────────────────────


def test_messages_only_valid():
	req = ChatCompletionRequest(model="openai/gpt-4", messages=[{"role": "user", "content": "hi"}])
	assert req.messages[0].content == "hi"
	assert req.prompt_id is None


def test_prompt_id_only_valid():
	pid = uuid4()
	req = ChatCompletionRequest(
		model="openai/gpt-4",
		prompt_id=pid,
		variables={"name": "Test"},
	)
	assert req.prompt_id == pid
	assert req.variables == {"name": "Test"}
	assert req.messages == []


def test_both_messages_and_prompt_id_invalid():
	with pytest.raises(ValidationError) as exc_info:
		ChatCompletionRequest(
			model="openai/gpt-4",
			messages=[{"role": "user", "content": "hi"}],
			prompt_id=uuid4(),
		)
	err = str(exc_info.value).lower()
	assert "mutually exclusive" in err or "prompt_id" in err


def test_neither_messages_nor_prompt_id_invalid():
	with pytest.raises(ValidationError) as exc_info:
		ChatCompletionRequest(model="openai/gpt-4")
	err = str(exc_info.value).lower()
	assert "provide either" in err or "messages" in err


# ── _resolve_prompt_template ─────────────────────────────────────────────────


class PromptTemplateFakeDB:
	"""FakeDB that returns a prompt template for execute(select(PromptTemplate...))."""

	def __init__(self, template=None):
		self._template = template

	async def execute(self, stmt, params=None):
		class Result:
			def __init__(inner_self, tpl):
				inner_self._tpl = tpl

			def scalar_one_or_none(inner_self):
				return inner_self._tpl

		return Result(self._template)

	async def scalar(self, *args, **kwargs):
		return None

	async def commit(self):
		pass


@pytest.mark.asyncio
async def test_resolve_prompt_template_success():
	"""prompt_id + variables → resolved [system?, user] messages with substituted content."""
	from app.services.llm_service import _resolve_prompt_template

	pid = uuid4()
	org_id = uuid4()
	tpl = SimpleNamespace(
		id=pid,
		org_id=org_id,
		system_message="You are {{role}}.",
		user_template="Say hello to {{name}}",
		is_active=True,
	)

	db = PromptTemplateFakeDB(template=tpl)
	messages = await _resolve_prompt_template(db, org_id, pid, {"role": "helper", "name": "Test"})

	assert len(messages) == 2
	assert messages[0].role == "system"
	assert messages[0].content == "You are helper."
	assert messages[1].role == "user"
	assert messages[1].content == "Say hello to Test"


@pytest.mark.asyncio
async def test_resolve_prompt_template_no_system_message():
	"""Template without system_message → only user message."""
	from app.services.llm_service import _resolve_prompt_template

	pid = uuid4()
	org_id = uuid4()
	tpl = SimpleNamespace(
		id=pid,
		org_id=org_id,
		system_message=None,
		user_template="Hello {{name}}",
		is_active=True,
	)

	db = PromptTemplateFakeDB(template=tpl)
	messages = await _resolve_prompt_template(db, org_id, pid, {"name": "Alice"})

	assert len(messages) == 1
	assert messages[0].role == "user"
	assert messages[0].content == "Hello Alice"


@pytest.mark.asyncio
async def test_resolve_prompt_template_not_found_404():
	"""prompt_id with no matching template → 404."""
	from fastapi import HTTPException

	from app.services.llm_service import _resolve_prompt_template

	class EmptyDB:
		async def execute(self, stmt, params=None):
			class Result:
				def scalar_one_or_none(self):
					return None
			return Result()

	db = EmptyDB()
	with pytest.raises(HTTPException) as exc_info:
		await _resolve_prompt_template(db, uuid4(), uuid4(), {})
	assert exc_info.value.status_code == 404
	detail = str(exc_info.value.detail).lower()
	assert "prompt_not_found" in detail or "prompt_id" in detail
