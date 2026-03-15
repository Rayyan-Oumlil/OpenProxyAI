from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .._client import OpenProxy
    from .._async_client import AsyncOpenProxy


class SyncAnalyticsResource:
    def __init__(self, client: "OpenProxy"):
        self._client = client

    def overview(self, period_days: int = 30) -> dict:
        return self._client._request(
            "GET", "/api/v1/analytics/overview", params={"period_days": period_days}
        ).json()

    def logs(self, page: int = 1, page_size: int = 50, **filters) -> dict:
        params = {
            "page": page,
            "page_size": page_size,
            **{k: v for k, v in filters.items() if v is not None},
        }
        return self._client._request("GET", "/api/v1/analytics/logs", params=params).json()


class AsyncAnalyticsResource:
    def __init__(self, client: "AsyncOpenProxy"):
        self._client = client

    async def overview(self, period_days: int = 30) -> dict:
        return (
            await self._client._request(
                "GET", "/api/v1/analytics/overview", params={"period_days": period_days}
            )
        ).json()

    async def logs(self, page: int = 1, page_size: int = 50, **filters) -> dict:
        params = {
            "page": page,
            "page_size": page_size,
            **{k: v for k, v in filters.items() if v is not None},
        }
        return (
            await self._client._request("GET", "/api/v1/analytics/logs", params=params)
        ).json()
