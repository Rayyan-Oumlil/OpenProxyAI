import respx
from openproxy import AsyncOpenProxy, OpenProxy, PolicyViolationError
import pytest
import httpx
from openproxy._streaming import _parse_chunk, _extract_gateway_meta
from openproxy.types.common import GatewayMeta


def make_gateway():
    return GatewayMeta(request_id="req-123", provider="openai")


def test_parse_chunk_content():
    line = 'data: {"id":"1","object":"chat.completion.chunk","created":1700000000,"model":"openai/gpt-4o","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}'
    chunk = _parse_chunk(line, make_gateway())
    assert chunk is not None
    assert chunk.choices[0].delta.content == "Hello"


def test_parse_chunk_done():
    chunk = _parse_chunk("data: [DONE]", make_gateway())
    assert chunk is None


def test_parse_chunk_non_data_line():
    chunk = _parse_chunk(": keep-alive", make_gateway())
    assert chunk is None


def test_extract_gateway_meta():
    headers = httpx.Headers({
        "x-openproxyai-request-id": "req-abc",
        "x-openproxyai-cost-usd": "0.001",
        "x-openproxyai-latency-ms": "123",
        "x-openproxyai-provider": "anthropic",
    })
    meta = _extract_gateway_meta(headers)
    assert meta.request_id == "req-abc"
    assert meta.cost_usd == pytest.approx(0.001)
    assert meta.latency_ms == 123
    assert meta.provider == "anthropic"


SSE = (
    'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"m","choices":[{"index":0,"delta":{"content":"Hel"},"finish_reason":null}]}\n\n'
    'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"m","choices":[{"index":0,"delta":{"content":"lo"},"finish_reason":null}]}\n\n'
    'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"m","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
    "data: [DONE]\n\n"
)
URL = "https://api.openproxyai.com/v1/chat/completions"
BODY = {"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True}


@respx.mock
def test_sync_stream_yields_every_chunk_and_closes():
    respx.post(URL).mock(return_value=httpx.Response(200, content=SSE.encode(), headers={"x-openproxyai-request-id": "req-1"}))
    stream = OpenProxy(api_key="k").chat.completions.create(**BODY)
    chunks = list(stream)
    assert "".join(c.choices[0].delta.content or "" for c in chunks) == "Hello"
    assert chunks[0].gateway.request_id == "req-1" and chunks[-1].choices[0].finish_reason == "stop"
    assert stream._response.is_closed


@respx.mock
def test_sync_stream_refusal_raises_the_typed_error_before_any_chunk():
    respx.post(URL).mock(return_value=httpx.Response(446, json={"error": "policy_violation", "reason_code": "pii_detected", "explanation": "No."}))
    with pytest.raises(PolicyViolationError) as caught:
        OpenProxy(api_key="k").chat.completions.create(**BODY)
    assert caught.value.explanation == "No."


@respx.mock
@pytest.mark.asyncio
async def test_async_stream_yields_every_chunk_not_just_the_first():
    respx.post(URL).mock(return_value=httpx.Response(200, content=SSE.encode()))
    stream = await AsyncOpenProxy(api_key="k").chat.completions.create(**BODY)
    text = [c.choices[0].delta.content async for c in stream if c.choices[0].delta.content]
    assert "".join(text) == "Hello"


@respx.mock
@pytest.mark.asyncio
async def test_async_stream_refusal_raises_the_typed_error():
    respx.post(URL).mock(return_value=httpx.Response(446, json={"error": "policy_violation", "reason_code": "x"}))
    with pytest.raises(PolicyViolationError):
        await AsyncOpenProxy(api_key="k").chat.completions.create(**BODY)
