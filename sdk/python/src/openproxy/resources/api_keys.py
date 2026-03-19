from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .._client import OpenProxy
    from .._async_client import AsyncOpenProxy


class SyncApiKeysResource:
    def __init__(self, client: "OpenProxy"):
        self._client = client

    def list(self) -> list[dict]:
        return self._client._request("GET", "/api/v1/api-keys").json()

    def create(self, name: str, permissions: list[str] | None = None, expires_at: str | None = None) -> dict:
        body: dict = {"name": name}
        if permissions is not None:
            body["permissions"] = permissions
        if expires_at is not None:
            body["expires_at"] = expires_at
        return self._client._request("POST", "/api/v1/api-keys", json=body).json()

    def delete(self, key_id: str) -> None:
        self._client._request("DELETE", f"/api/v1/api-keys/{key_id}")


class AsyncApiKeysResource:
    def __init__(self, client: "AsyncOpenProxy"):
        self._client = client

    async def list(self) -> list[dict]:
        return (await self._client._request("GET", "/api/v1/api-keys")).json()

    async def create(self, name: str, permissions: list[str] | None = None, expires_at: str | None = None) -> dict:
        body: dict = {"name": name}
        if permissions is not None:
            body["permissions"] = permissions
        if expires_at is not None:
            body["expires_at"] = expires_at
        return (await self._client._request("POST", "/api/v1/api-keys", json=body)).json()

    async def delete(self, key_id: str) -> None:
        await self._client._request("DELETE", f"/api/v1/api-keys/{key_id}")
