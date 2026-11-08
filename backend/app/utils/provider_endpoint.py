"""Validation of a provider key's custom ``api_base``: where an org admin may point the gateway.

External endpoints follow the same rule as webhooks (https, public address). Internal endpoints (vLLM, Ollama,
a private gateway) may be private or plain http, but only when the operator enabled them, and never link-local,
multicast or unspecified addresses (cloud metadata lives there).

``validate_api_base`` runs at save time. ``filter_allowed_endpoints`` repeats it at call time (cached for a short
while), so a hostname that later resolves to a private address, or an operator who turns the internal switch off,
stops a key from being used. It cannot close the gap between that check and LiteLLM's own DNS lookup, nor stop
redirects: that needs egress control (see docs/plan/phase-2-plan.md).
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
from collections.abc import Sequence
from typing import Protocol, TypeVar
from urllib.parse import urlparse

from app.config import settings
from app.utils.ssrf import resolve_public_ip

logger = logging.getLogger(__name__)

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


# ── call-time re-check ───────────────────────────────────────────────────────

_RUNTIME_TTL_SECONDS = 30.0
_RUNTIME_CACHE_MAX = 1024
_runtime_cache: dict[tuple[str, bool], tuple[float, bool]] = {}


class _HasEndpoint(Protocol):
	api_base: str | None
	is_internal: bool


K = TypeVar("K", bound=_HasEndpoint)


def clear_runtime_cache() -> None:
	_runtime_cache.clear()


async def _still_allowed(api_base: str, is_internal: bool) -> bool:
	now = time.monotonic()
	cached = _runtime_cache.get((api_base, is_internal))
	if cached is not None and now - cached[0] < _RUNTIME_TTL_SECONDS:
		return cached[1]
	allowed = await validate_api_base(api_base, is_internal=is_internal) is None
	if len(_runtime_cache) >= _RUNTIME_CACHE_MAX:
		_runtime_cache.clear()
	_runtime_cache[(api_base, is_internal)] = (now, allowed)
	return allowed


async def api_base_still_allowed(api_base: str, *, is_internal: bool) -> bool:
	return await _still_allowed(api_base, is_internal)


async def filter_allowed_endpoints(keys: Sequence[K]) -> tuple[list[K], int]:
	"""Keep keys that use the provider's own endpoint or whose custom endpoint still validates.

	Returns (kept, dropped_count). Callers must treat "every key dropped" as an error, never as a reason to try
	some other credential: that would send data meant for a private endpoint somewhere else.
	"""
	kept: list[K] = []
	dropped = 0
	for key in keys:
		if key.api_base and not await _still_allowed(key.api_base, key.is_internal):
			logger.warning("provider key skipped: its api_base no longer passes validation (key=%s)", getattr(key, "id", "?"))
			dropped += 1
			continue
		kept.append(key)
	return kept, dropped
