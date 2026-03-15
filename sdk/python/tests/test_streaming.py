import pytest
import respx
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
