"""Validation of a provider key's custom ``api_base``: where an org admin may point the gateway.

External endpoints follow the same rule as webhooks (https, public address). Internal endpoints (vLLM, Ollama,
a private gateway) may be private or plain http, but only when the operator enabled them, and never link-local,
multicast or unspecified addresses (cloud metadata lives there).

This checks at save time. LiteLLM resolves the host again when it calls, so a hostname that later resolves
somewhere else is not caught here.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from app.config import settings
from app.utils.ssrf import resolve_public_ip

_ALWAYS_BLOCKED_NETWORKS = [
	ipaddress.ip_network("169.254.0.0/16"),  # link-local, incl. the cloud metadata address
	ipaddress.ip_network("fe80::/10"),
	ipaddress.ip_network("fd00:ec2::/32"),  # AWS IPv6 metadata
]


def _never_allowed(ip_str: str) -> bool:
	ip = ipaddress.ip_address(ip_str.split("%", 1)[0])
	# ::ffff:169.254.169.254 is the metadata address in IPv6 clothing: judge the IPv4 address inside it.
	if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
		ip = ip.ipv4_mapped
	return ip.is_unspecified or ip.is_multicast or ip.is_link_local or any(ip in net for net in _ALWAYS_BLOCKED_NETWORKS)


def _resolve(host: str, port: int) -> list[str]:
	try:
		return [info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
	except (OSError, UnicodeError):
		return []


async def validate_api_base(api_base: str, *, is_internal: bool) -> str | None:
	"""Return a human-readable reason the endpoint is not allowed, or None when it is."""
	try:
		parsed = urlparse(api_base)
		port = parsed.port
	except ValueError:
		return "api_base is not a valid URL"
	if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
		return "api_base must be an http(s) URL with a host"
	if parsed.username is not None or parsed.password is not None:
		return "api_base must not contain credentials"
	if parsed.query or parsed.fragment:
		return "api_base must not contain a query string or fragment"

	if is_internal:
		if not settings.ALLOW_INTERNAL_PROVIDER_ENDPOINTS:
			return "Internal endpoints are not enabled on this gateway (operator setting ALLOW_INTERNAL_PROVIDER_ENDPOINTS)"
		ips = await asyncio.to_thread(_resolve, parsed.hostname, port or (443 if parsed.scheme == "https" else 80))
		if not ips:
			return "api_base host does not resolve"
		if any(_never_allowed(ip) for ip in ips):
			return "api_base must not point at a link-local, multicast or unspecified address"
		return None

	if settings.AIRGAP_MODE:
		return "External endpoints are not allowed in air-gapped mode; mark the key internal"
	if parsed.scheme.lower() != "https":
		return "api_base must use https unless the key is marked internal"
	if await resolve_public_ip(api_base) is None:
		return "api_base must resolve to a public address"
	return None
