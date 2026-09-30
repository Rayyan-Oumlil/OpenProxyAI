"""Outbound URL guard: HTTPS only, no private, loopback, link-local or CGN destinations.

Shared by webhook delivery and the MCP gateway (both call URLs that org admins configure).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_EXTRA_BLOCKED_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-Grade NAT (RFC 6598)
]


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
