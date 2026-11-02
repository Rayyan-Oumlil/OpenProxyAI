"""Pin the litellm surface the gateway depends on; a litellm upgrade that breaks it fails here, not in prod."""
import inspect

import litellm
import pytest


def _params(fn) -> set[str]:
    return set(inspect.signature(fn).parameters)


def test_cost_per_token_accepts_budget_preflight_arguments():
    assert {"model", "prompt_tokens", "completion_tokens"} <= _params(litellm.cost_per_token)
    prompt_cost, completion_cost = litellm.cost_per_token(model="gpt-4o-mini", prompt_tokens=10, completion_tokens=10)
    assert prompt_cost > 0 and completion_cost > 0


def test_token_counter_supports_messages_and_text():
    assert {"model", "messages", "text"} <= _params(litellm.token_counter)
    assert litellm.token_counter(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi there"}]) > 0
    assert litellm.token_counter(model="gpt-4o-mini", text="hi there") > 0


@pytest.mark.parametrize("name", ["acompletion", "aembedding"])
def test_async_entry_points_exist_and_are_coroutines(name):
    assert inspect.iscoroutinefunction(getattr(litellm, name))
