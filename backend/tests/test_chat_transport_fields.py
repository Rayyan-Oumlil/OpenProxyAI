"""A caller's request body must never choose where, or with whose credentials, the gateway calls a provider."""

from types import SimpleNamespace

import pytest

from app.schemas.chat import ChatCompletionRequest
from app.services import behavior as bh
from app.services.llm_service import LLMService

FIELDS = ["api_base", "base_url", "api_key", "api_version", "client", "custom_llm_provider", "extra_headers", "headers", "organization"]


def _ctx(request, behavior=None):
	return SimpleNamespace(request=request, behavior=behavior, behavior_plan=None)


def _request(**extra):
	return ChatCompletionRequest(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}], **extra)


def test_the_list_covers_every_transport_field():
	assert set(FIELDS) <= set(bh.TRANSPORT_FIELDS)


@pytest.mark.parametrize("field", FIELDS)
def test_a_transport_field_in_the_body_never_reaches_the_provider_call(field):
	kwargs = LLMService._provider_kwargs(_ctx(_request(**{field: "http://attacker.example/v1"})), "openai/gpt-4o")
	assert field not in kwargs


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("ceiling", [None, bh.Behavior(creativity="low")])
def test_nor_when_behavior_settings_or_a_ceiling_are_active(field, ceiling):
	resolved = bh.resolve(bh.Behavior(creativity="high"), bh.Behavior(), ceiling or bh.Behavior())
	kwargs = LLMService._provider_kwargs(_ctx(_request(**{field: "x"}), resolved), "openai/gpt-4o")
	assert field not in kwargs


def test_the_gateways_own_settings_and_ordinary_parameters_are_kept():
	kwargs = LLMService._provider_kwargs(_ctx(_request(temperature=0.3, seed=7)), "openai/gpt-4o")
	assert kwargs["model"] == "openai/gpt-4o" and kwargs["timeout"] == 30 and kwargs["request_timeout"] == 30
	assert kwargs["temperature"] == 0.3 and kwargs["seed"] == 7


def test_timeouts_survive_a_ceiling():
	resolved = bh.resolve(bh.Behavior(), bh.Behavior(), bh.Behavior(creativity="low"))
	kwargs = LLMService._provider_kwargs(_ctx(_request(), resolved), "openai/gpt-4o")
	assert kwargs["timeout"] == 30 and kwargs["request_timeout"] == 30 and kwargs["model"] == "openai/gpt-4o"
