import pytest
import respx
import httpx
from openproxy import OpenProxy
from openproxy._exceptions import PolicyViolationError, RateLimitError, BudgetExceededError
from openproxy.types.chat import ChatCompletion


CHAT_RESPONSE = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "openai/gpt-4o",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}


@respx.mock
def test_chat_completion_success():
    respx.post("https://api.openproxyai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=CHAT_RESPONSE,
            headers={
                "x-openproxyai-cost-usd": "0.000150",
                "x-openproxyai-latency-ms": "450",
                "x-openproxyai-provider": "openai",
            },
        )
    )
    client = OpenProxy(api_key="opai_test")
    response = client.chat.completions.create(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    assert isinstance(response, ChatCompletion)
    assert response.choices[0].message.content == "Hello!"
    assert response.gateway.cost_usd == pytest.approx(0.000150, rel=1e-3)
    assert response.gateway.provider == "openai"


@respx.mock
def test_policy_violation_error():
    respx.post("https://api.openproxyai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            403,
            json={
                "error": "policy_violation",
                "detail": "Blocked keyword detected",
                "reason_code": "blocked_keyword",
                "triggered_rules": ["keyword:confidential"],
            },
        )
    )
    client = OpenProxy(api_key="opai_test")
    with pytest.raises(PolicyViolationError) as exc_info:
        client.chat.completions.create(model="openai/gpt-4o", messages=[{"role": "user", "content": "test"}])
    assert exc_info.value.reason_code == "blocked_keyword"
    assert "keyword:confidential" in exc_info.value.triggered_rules


@respx.mock
def test_rate_limit_error():
    respx.post("https://api.openproxyai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={"error": "rate_limit_exceeded", "limit_type": "requests_per_minute", "detail": "Too many requests", "retry_after": 30},
        )
    )
    client = OpenProxy(api_key="opai_test")
    with pytest.raises(RateLimitError) as exc_info:
        client.chat.completions.create(model="openai/gpt-4o", messages=[])
    assert exc_info.value.retry_after == 30


@respx.mock
def test_budget_exceeded_error():
    respx.post("https://api.openproxyai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={"error": "rate_limit_exceeded", "limit_type": "budget_daily_usd", "detail": "Budget exceeded", "retry_after": 3600},
        )
    )
    client = OpenProxy(api_key="opai_test")
    with pytest.raises(BudgetExceededError):
        client.chat.completions.create(model="openai/gpt-4o", messages=[])
