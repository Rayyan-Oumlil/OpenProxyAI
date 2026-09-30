"""Shared outbound-URL guard used by webhooks and the MCP gateway."""

import pytest

from app.utils import ssrf


def _resolve_to(monkeypatch, ip: str) -> None:
	monkeypatch.setattr(ssrf.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (ip, 443))])


def test_public_https_url_is_allowed(monkeypatch):
	_resolve_to(monkeypatch, "93.184.216.34")
	assert ssrf.is_safe_https_url("https://mcp.example.com/mcp") is True


@pytest.mark.parametrize("url", ["http://mcp.example.com/mcp", "ftp://x.example.com", "https:///nohost", "not a url"])
def test_non_https_or_malformed_urls_are_rejected(url):
	assert ssrf.is_safe_https_url(url) is False


@pytest.mark.parametrize("ip", ["10.0.0.5", "127.0.0.1", "169.254.169.254", "100.64.0.1", "::1", "192.168.1.10"])
def test_private_loopback_link_local_and_cgn_are_rejected(monkeypatch, ip):
	_resolve_to(monkeypatch, ip)
	assert ssrf.is_safe_https_url("https://looks-public.example.com/mcp") is False


def test_unresolvable_host_is_rejected(monkeypatch):
	def boom(*a, **k):  # noqa: ARG001
		raise OSError("no such host")

	monkeypatch.setattr(ssrf.socket, "getaddrinfo", boom)
	assert ssrf.is_safe_https_url("https://nope.invalid/mcp") is False
