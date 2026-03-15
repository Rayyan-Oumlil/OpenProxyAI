from __future__ import annotations
import time
import httpx

from ._base_client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    _raise_for_status,
    _should_retry,
    _backoff,
)
from ._streaming import SyncStream, _extract_gateway_meta
from ._exceptions import OpenProxyError
from .resources.chat import SyncChatResource
from .resources.embeddings import SyncEmbeddingsResource
from .resources.api_keys import SyncApiKeysResource
from .resources.analytics import SyncAnalyticsResource


class OpenProxy:
    """Synchronous OpenProxy client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )
        self.chat = SyncChatResource(self)
        self.embeddings = SyncEmbeddingsResource(self)
        self.api_keys = SyncApiKeysResource(self)
        self.analytics = SyncAnalyticsResource(self)

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._http.request(method, path, **kwargs)
                _raise_for_status(response)
                return response
            except OpenProxyError as exc:
                if _should_retry(exc, attempt):
                    time.sleep(_backoff(attempt))
                    continue
                raise
            except Exception as exc:
                if _should_retry(exc, attempt):
                    time.sleep(_backoff(attempt))
                    continue
                raise
        raise RuntimeError("Max retries exceeded")

    def _stream(self, path: str, json_body: dict) -> SyncStream:
        response = self._http.stream("POST", path, json=json_body)
        # Enter the context manager to get the actual response
        ctx = response.__enter__()
        return SyncStream(ctx)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
