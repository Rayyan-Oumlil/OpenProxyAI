from __future__ import annotations
import asyncio
import httpx

from ._base_client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    _raise_for_status,
    _should_retry,
    _backoff,
)
from ._streaming import AsyncStream
from ._exceptions import OpenProxyError
from .resources.chat import AsyncChatResource
from .resources.embeddings import AsyncEmbeddingsResource
from .resources.api_keys import AsyncApiKeysResource
from .resources.analytics import AsyncAnalyticsResource


class AsyncOpenProxy:
    """Asynchronous OpenProxy client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )
        self.chat = AsyncChatResource(self)
        self.embeddings = AsyncEmbeddingsResource(self)
        self.api_keys = AsyncApiKeysResource(self)
        self.analytics = AsyncAnalyticsResource(self)

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._http.request(method, path, **kwargs)
                _raise_for_status(response)
                return response
            except OpenProxyError as exc:
                if _should_retry(exc, attempt):
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise
            except Exception as exc:
                if _should_retry(exc, attempt):
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise
        raise RuntimeError("Max retries exceeded")

    async def _stream(self, path: str, json_body: dict) -> AsyncStream:
        response = self._http.stream("POST", path, json=json_body)
        ctx = await response.__aenter__()
        return AsyncStream(ctx)

    async def close(self):
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
