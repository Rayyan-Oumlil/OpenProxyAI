from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..._client import OpenProxy
    from ..._async_client import AsyncOpenProxy

from ..._streaming import SyncStream, AsyncStream, _extract_gateway_meta
from ...types.chat import ChatCompletion, Choice, Message, Usage


def _parse_completion(body: dict, headers) -> ChatCompletion:
    choices = []
    for c in body.get("choices", []):
        msg = c.get("message", {})
        choices.append(Choice(
            index=c.get("index", 0),
            message=Message(role=msg.get("role", "assistant"), content=msg.get("content", "")),
            finish_reason=c.get("finish_reason"),
        ))
    usage_data = body.get("usage", {})
    return ChatCompletion(
        id=body.get("id", ""),
        object=body.get("object", "chat.completion"),
        created=body.get("created", 0),
        model=body.get("model", ""),
        choices=choices,
        usage=Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        ),
        gateway=_extract_gateway_meta(headers),
    )


class SyncChatCompletionsResource:
    def __init__(self, client: "OpenProxy"):
        self._client = client

    def create(self, model: str, messages: list[dict], stream: bool = False, **kwargs) -> ChatCompletion | SyncStream:
        body = {"model": model, "messages": messages, "stream": stream, **kwargs}
        if stream:
            return self._client._stream("/v1/chat/completions", body)
        response = self._client._request("POST", "/v1/chat/completions", json=body)
        return _parse_completion(response.json(), response.headers)


class AsyncChatCompletionsResource:
    def __init__(self, client: "AsyncOpenProxy"):
        self._client = client

    async def create(self, model: str, messages: list[dict], stream: bool = False, **kwargs) -> ChatCompletion | AsyncStream:
        body = {"model": model, "messages": messages, "stream": stream, **kwargs}
        if stream:
            return await self._client._stream("/v1/chat/completions", body)
        response = await self._client._request("POST", "/v1/chat/completions", json=body)
        return _parse_completion(response.json(), response.headers)
