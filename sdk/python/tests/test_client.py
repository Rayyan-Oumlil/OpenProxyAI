import pytest
import respx
import httpx
from openproxy import OpenProxy
from openproxy._exceptions import AuthError


def test_client_init():
    client = OpenProxy(api_key="opai_test")
    assert client.api_key == "opai_test"
    assert "openproxyai.com" in client.base_url


@respx.mock
def test_client_sets_auth_header():
    respx.get("https://api.openproxyai.com/api/v1/api-keys").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = OpenProxy(api_key="opai_mykey")
    client.api_keys.list()
    assert respx.calls[0].request.headers["authorization"] == "Bearer opai_mykey"


@respx.mock
def test_auth_error_on_401():
    respx.post("https://api.openproxyai.com/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized", "detail": "Invalid API key"})
    )
    client = OpenProxy(api_key="opai_bad")
    with pytest.raises(AuthError):
        client.chat.completions.create(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])


@respx.mock
def test_api_error_on_500():
    respx.post("https://api.openproxyai.com/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "internal", "detail": "oops"})
    )
    client = OpenProxy(api_key="opai_test")
    with pytest.raises(Exception):
        client.chat.completions.create(model="openai/gpt-4o", messages=[])
