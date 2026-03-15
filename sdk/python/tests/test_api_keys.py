import pytest
import respx
import httpx
from openproxy import OpenProxy


API_KEY_RESPONSE = {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "My Key",
    "key_prefix": "opai_test",
    "permissions": ["proxy:llm"],
    "is_active": True,
    "expires_at": None,
    "created_at": "2026-01-01T00:00:00",
}


@respx.mock
def test_list_api_keys():
    respx.get("https://api.openproxyai.com/api/v1/api-keys").mock(
        return_value=httpx.Response(200, json=[API_KEY_RESPONSE])
    )
    client = OpenProxy(api_key="opai_test")
    keys = client.api_keys.list()
    assert len(keys) == 1
    assert keys[0]["name"] == "My Key"


@respx.mock
def test_create_api_key():
    created = {**API_KEY_RESPONSE, "key": "opai_fulllongkey123"}
    respx.post("https://api.openproxyai.com/api/v1/api-keys").mock(
        return_value=httpx.Response(201, json=created)
    )
    client = OpenProxy(api_key="opai_test")
    result = client.api_keys.create(name="My Key")
    assert result["key"] == "opai_fulllongkey123"


@respx.mock
def test_delete_api_key():
    key_id = "550e8400-e29b-41d4-a716-446655440000"
    respx.delete(f"https://api.openproxyai.com/api/v1/api-keys/{key_id}").mock(
        return_value=httpx.Response(204)
    )
    client = OpenProxy(api_key="opai_test")
    client.api_keys.delete(key_id)  # Should not raise
