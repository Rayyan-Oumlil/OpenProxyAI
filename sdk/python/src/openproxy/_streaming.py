from __future__ import annotations
import json
from typing import Iterator, TYPE_CHECKING
if TYPE_CHECKING:
    import httpx

from .types.chat import ChatCompletionChunk, Choice, Delta, Usage
from .types.common import GatewayMeta


def _parse_chunk(line: str, gateway_meta: GatewayMeta) -> ChatCompletionChunk | None:
    line = line.strip()
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if data == "[DONE]":
        return None
    try:
        body = json.loads(data)
    except json.JSONDecodeError:
        return None

    choices = []
    for c in body.get("choices", []):
        delta_data = c.get("delta", {})
        choices.append(Choice(
            index=c.get("index", 0),
            delta=Delta(role=delta_data.get("role"), content=delta_data.get("content")),
            finish_reason=c.get("finish_reason"),
        ))

    usage_data = body.get("usage")
    usage = None
    if usage_data:
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

    return ChatCompletionChunk(
        id=body.get("id", ""),
        object=body.get("object", "chat.completion.chunk"),
        created=body.get("created", 0),
        model=body.get("model", ""),
        choices=choices,
        usage=usage,
        gateway=gateway_meta,
    )


class SyncStream:
    def __init__(self, response: "httpx.Response"):
        self._response = response
        self._gateway = _extract_gateway_meta(response.headers)

    def __iter__(self) -> Iterator[ChatCompletionChunk]:
        for line in self._response.iter_lines():
            chunk = _parse_chunk(line, self._gateway)
            if chunk is not None:
                yield chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._response.close()


class AsyncStream:
    def __init__(self, response: "httpx.Response"):
        self._response = response
        self._gateway = _extract_gateway_meta(response.headers)

    def __aiter__(self) -> "AsyncStream":
        return self

    async def __anext__(self) -> ChatCompletionChunk:
        async for line in self._response.aiter_lines():
            chunk = _parse_chunk(line, self._gateway)
            if chunk is not None:
                return chunk
        raise StopAsyncIteration

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._response.aclose()


def _extract_gateway_meta(headers) -> GatewayMeta:
    def _int(v):
        try:
            return int(v)
        except Exception:
            return None

    def _float(v):
        try:
            return float(v)
        except Exception:
            return None

    return GatewayMeta(
        request_id=headers.get("x-openproxyai-request-id"),
        cost_usd=_float(headers.get("x-openproxyai-cost-usd")),
        latency_ms=_int(headers.get("x-openproxyai-latency-ms")),
        provider=headers.get("x-openproxyai-provider"),
        model=headers.get("x-openproxyai-model"),
        policy_action=headers.get("x-openproxyai-policy-action"),
        policy_reason=headers.get("x-openproxyai-policy-reason"),
        ttft_ms=_int(headers.get("x-openproxyai-ttft-ms")),
        cache=headers.get("x-openproxyai-cache"),
    )
