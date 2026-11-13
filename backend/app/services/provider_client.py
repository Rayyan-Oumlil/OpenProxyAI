"""The connection guard for custom provider endpoints: where the gateway may actually connect, checked per request.

Save-time validation (``app/utils/provider_endpoint.py``) cannot be enough on its own. A hostname can resolve to a
private address after it was saved, and an endpoint that passed can answer ``307`` and send the request, prompt
included, somewhere else. So calls to a custom endpoint go through a client that

* never follows a redirect (a 3xx is an error to the caller, and nothing is re-sent);
* resolves the host itself for every request, requires every answer to be an allowed address, and connects to
  that validated address, so there is no gap between the check and the connection;
* still verifies TLS against the original hostname (``sni_hostname``), not the address it connected to;
* re-reads the operator's ``ALLOW_INTERNAL_PROVIDER_ENDPOINTS`` switch on every request.

It applies to OpenAI-compatible endpoints (vLLM, Ollama's ``/v1``, private gateways), which LiteLLM reaches through
the OpenAI SDK where a client can be supplied. Other providers cannot take a guarded client, so they cannot have a
custom endpoint.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
import weakref
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.utils.ssrf import ip_allowed

Resolver = Callable[[str, int], Awaitable[list[str]]]

CUSTOM_ENDPOINT_PROVIDER = "openai"  # the provider name for any OpenAI-compatible server
_CLIENTS_PER_LOOP = 32
_TIMEOUT = httpx.Timeout(600.0, connect=5.0)  # the OpenAI SDK's own defaults; LiteLLM sets the real timeout per call


class EgressRefused(httpx.TransportError):
	"""The destination is one the gateway may not connect to. A connection failure to callers, never a redirect or retry."""


@dataclass(frozen=True)
class ProviderEndpoint:
	api_base: str
	is_internal: bool


async def _system_resolver(host: str, port: int) -> list[str]:
	def lookup() -> list[str]:
		try:
			return [info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
		except (OSError, UnicodeError):
			return []

	return await asyncio.to_thread(lookup)


def _is_ip(host: str) -> bool:
	try:
		ipaddress.ip_address(host)
		return True
	except ValueError:
		return False


class GuardedTransport(httpx.AsyncBaseTransport):
	def __init__(
		self, *, internal: bool, inner: httpx.AsyncBaseTransport | None = None, resolver: Resolver | None = None, verify=True,
	) -> None:
		self._internal = internal
		self._inner = inner if inner is not None else httpx.AsyncHTTPTransport(verify=verify, retries=0)
		self._resolve = resolver or _system_resolver

	async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
		url = request.url
		host = url.host
		port = url.port or (443 if url.scheme == "https" else 80)
		addresses = [host] if _is_ip(host) else await self._resolve(host, port)
		allow_private = self._internal and settings.ALLOW_INTERNAL_PROVIDER_ENDPOINTS
		if not addresses or not all(ip_allowed(address, internal=allow_private) for address in addresses):
			raise EgressRefused(f"{host} is not an address the gateway may connect to", request=request)
		request.url = url.copy_with(host=addresses[0])  # connect to what was validated; the Host header keeps the name
		request.extensions = {**request.extensions, "sni_hostname": host}  # and TLS is checked against the name
		return await self._inner.handle_async_request(request)

	async def aclose(self) -> None:
		await self._inner.aclose()


def guarded_http_client(
	*, internal: bool, resolver: Resolver | None = None, verify=True, inner: httpx.AsyncBaseTransport | None = None,
	timeout: httpx.Timeout | float | None = None,
) -> httpx.AsyncClient:
	return httpx.AsyncClient(
		transport=GuardedTransport(internal=internal, inner=inner, resolver=resolver, verify=verify),
		follow_redirects=False,
		timeout=_TIMEOUT if timeout is None else timeout,
	)


# One client per (key, endpoint) keeps connections alive between requests. It belongs to the event loop that made it.
_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, OrderedDict[tuple[str, ProviderEndpoint], AsyncOpenAI]] = weakref.WeakKeyDictionary()


def openai_client_for(api_key: str, endpoint: ProviderEndpoint) -> AsyncOpenAI:
	"""An OpenAI SDK client for a custom endpoint, whose connections all go through the guard. Call from async code."""
	cache = _clients.setdefault(asyncio.get_running_loop(), OrderedDict())
	cache_key = (hashlib.sha256(api_key.encode()).hexdigest(), endpoint)
	client = cache.get(cache_key)
	if client is not None:
		cache.move_to_end(cache_key)
		return client
	client = AsyncOpenAI(
		api_key=api_key, base_url=endpoint.api_base, http_client=guarded_http_client(internal=endpoint.is_internal), max_retries=0,
	)
	cache[cache_key] = client
	while len(cache) > _CLIENTS_PER_LOOP:
		cache.popitem(last=False)
	return client
