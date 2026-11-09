"""Outbound URL guard: HTTPS only, no private, loopback, link-local or CGN destinations.

Shared by webhook delivery and the MCP gateway (both call URLs that org admins configure).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

_EXTRA_BLOCKED_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-Grade NAT (RFC 6598)
]


_NEVER_ALLOWED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),  # link-local, incl. the cloud metadata address
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fd00:ec2::/32"),  # AWS IPv6 metadata
]


def _parse_ip(ip_str: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """An address, with an IPv4-mapped IPv6 address (``::ffff:10.0.0.5``) judged as the IPv4 address inside it."""
    try:
        ip = ipaddress.ip_address(ip_str.split("%", 1)[0])
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def never_allowed_ip(ip_str: str) -> bool:
    """Addresses nothing may reach, not even a private endpoint the operator enabled: cloud metadata and its kin."""
    ip = _parse_ip(ip_str)
    if ip is None:
        return True
    return ip.is_unspecified or ip.is_multicast or ip.is_link_local or any(ip in net for net in _NEVER_ALLOWED_NETWORKS)


def ip_allowed(ip_str: str, *, internal: bool) -> bool:
    """May the gateway connect to this address? Public ones always; private ones only for an internal endpoint."""
    if never_allowed_ip(ip_str):
        return False
    return internal or not is_private_or_local_ip(ip_str)


def is_private_or_local_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return True
    return any(ip in net for net in _EXTRA_BLOCKED_NETWORKS)


def resolve_safe_url(url: str) -> tuple[bool, str | None]:
    """Resolve the hostname and reject private/local/CGN IPs.

    Returns (is_safe, first_resolved_ip_str). The resolved IP is used only for validation;
    the request itself goes to the original URL so TLS hostname verification works normally.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, None
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return False, None
    try:
        port = parsed.port or 443  # raises ValueError for out-of-range or non-numeric ports
        addr_infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError, ValueError):  # gaierror is an OSError; IDNA failures are UnicodeError
        return False, None
    if not addr_infos:
        return False, None
    for info in addr_infos:
        sockaddr = info[4]
        if not sockaddr or is_private_or_local_ip(sockaddr[0]):
            return False, None
    return True, addr_infos[0][4][0]


def is_safe_https_url(url: str) -> bool:
    return resolve_safe_url(url)[0]


async def resolve_public_ip(url: str) -> str | None:
    """Validate ``url`` and return the public IP to connect to, or None if it is unsafe.

    Resolution runs in a worker thread (getaddrinfo blocks). Callers must connect to the returned
    address instead of resolving the hostname again, which closes the DNS-rebinding window.
    """
    safe, ip = await asyncio.to_thread(resolve_safe_url, url)
    return ip if safe else None
