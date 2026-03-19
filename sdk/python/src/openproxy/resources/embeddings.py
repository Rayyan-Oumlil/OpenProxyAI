from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .._client import OpenProxy
    from .._async_client import AsyncOpenProxy


class SyncEmbeddingsResource:
    def __init__(self, client: "OpenProxy"):
        self._client = client

    def create(self, model: str, input: str | list[str], **kwargs) -> dict:
        body = {"model": model, "input": input, **kwargs}
        response = self._client._request("POST", "/v1/embeddings", json=body)
        return response.json()


class AsyncEmbeddingsResource:
    def __init__(self, client: "AsyncOpenProxy"):
        self._client = client

    async def create(self, model: str, input: str | list[str], **kwargs) -> dict:
        body = {"model": model, "input": input, **kwargs}
        response = await self._client._request("POST", "/v1/embeddings", json=body)
        return response.json()
