"""Every outbound call whose URL an org admin or an IdP can influence must connect only to a public address.

Each test runs a real listener on 127.0.0.1 and asserts the gateway never opens a connection to it, including when
DNS first answers with a public address and then with a private one (rebinding).
"""

from __future__ import annotations

import asyncio
import socket

import httpx
import pytest
from fastapi import HTTPException

from app.services import spend_report_service, sso_service, webhook_service

PUBLIC_IP = "93.184.216.34"


class _Listener:
    def __init__(self) -> None:
        self.connections = 0
        self.port = 0
        self._server: asyncio.AbstractServer | None = None

    async def __aenter__(self) -> "_Listener":
        async def handle(reader, writer):
            self.connections += 1
            writer.close()

        self._server = await asyncio.start_server(handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc) -> None:
        self._server.close()
        await self._server.wait_closed()


@pytest.fixture
def rebinding_dns(monkeypatch):
    """rebind.test answers with a public address once, then with loopback (a classic DNS-rebinding answer)."""
    real = socket.getaddrinfo
    calls = {"n": 0}

    def fake(host, port, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else host
        if name != "rebind.test":
            return real(host, port, *args, **kwargs)
        calls["n"] += 1
        ip = PUBLIC_IP if calls["n"] == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


async def test_webhook_delivery_survives_dns_rebinding(rebinding_dns, monkeypatch):
    monkeypatch.setattr(webhook_service, "_BASE_DELAY", 0)
    async with _Listener() as listener:
        status, _ = await webhook_service._deliver(f"https://rebind.test:{listener.port}/hook", {"event": "x"}, "")
        await asyncio.sleep(0.1)
    assert status == "failed"
    assert listener.connections == 0


async def test_spend_report_webhook_refuses_a_private_address():
    async with _Listener() as listener:
        sent = await spend_report_service._send_to_slack(f"https://127.0.0.1:{listener.port}/hook", {"text": "x"})
        await asyncio.sleep(0.1)
    assert sent is False
    assert listener.connections == 0


async def test_oidc_discovery_refuses_a_private_issuer():
    async with _Listener() as listener:
        with pytest.raises(HTTPException) as exc:
            await sso_service._fetch_oidc_config(f"https://127.0.0.1:{listener.port}")
        await asyncio.sleep(0.1)
    assert exc.value.status_code == 502
    assert listener.connections == 0


async def test_oidc_discovery_survives_dns_rebinding(rebinding_dns):
    async with _Listener() as listener:
        with pytest.raises(HTTPException):
            await sso_service._fetch_oidc_config(f"https://rebind.test:{listener.port}")
        await asyncio.sleep(0.1)
    assert listener.connections == 0


@pytest.mark.parametrize(
    "url",
    [
        "http://idp.example.com/token",
        "https://127.0.0.1/token",
        "https://169.254.169.254/latest/meta-data",
        "https://localhost/jwks",
        "",
    ],
)
def test_endpoints_named_by_a_discovery_document_must_be_public_https(url):
    with pytest.raises(HTTPException) as exc:
        sso_service.require_public_https_endpoint(url, "token_endpoint")
    assert exc.value.status_code == 502


def test_a_public_https_endpoint_is_accepted():
    sso_service.require_public_https_endpoint("https://8.8.8.8/token", "token_endpoint")


async def test_creating_an_sso_connection_refuses_a_private_issuer():
    with pytest.raises(HTTPException) as exc:
        await sso_service.create_sso_connection(
            db=None, org_id="o", provider_name="x", issuer_url="https://169.254.169.254", client_id="c",
            client_secret="s", domain_hint=None,
        )
    assert exc.value.status_code == 400


def test_httpx_is_still_importable_for_the_guarded_client():
    assert httpx.AsyncClient
