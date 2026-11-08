"""api_base validation for provider keys: what an org admin may point a key at."""

import pytest

from app.config import settings
from app.utils.provider_endpoint import validate_api_base


@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
	monkeypatch.setattr(settings, "AIRGAP_MODE", False)
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", False)


# ── external endpoints ───────────────────────────────────────────────────────


async def test_public_https_endpoint_is_accepted():
	assert await validate_api_base("https://8.8.8.8/v1", is_internal=False) is None


@pytest.mark.parametrize(
	"url",
	[
		"http://8.8.8.8/v1",  # not https
		"https://10.0.0.5/v1",  # private
		"https://127.0.0.1/v1",  # loopback
		"https://169.254.169.254/latest",  # cloud metadata
		"https://user:pw@8.8.8.8/v1",  # credentials in the URL
		"https://8.8.8.8/v1?x=1",  # query
		"https://8.8.8.8/v1#frag",  # fragment
		"ftp://8.8.8.8/v1",  # not http(s)
		"not a url",
		"https:///v1",  # no host
	],
)
async def test_unsafe_external_endpoints_are_rejected(url):
	assert await validate_api_base(url, is_internal=False) is not None


async def test_external_endpoint_is_refused_in_airgap_mode(monkeypatch):
	monkeypatch.setattr(settings, "AIRGAP_MODE", True)
	error = await validate_api_base("https://8.8.8.8/v1", is_internal=False)
	assert error and "air-gapped" in error


# ── internal endpoints (vLLM, Ollama, private gateways) ──────────────────────


async def test_internal_endpoints_are_off_unless_the_operator_enables_them():
	error = await validate_api_base("http://10.0.0.5:8000/v1", is_internal=True)
	assert error and "ALLOW_INTERNAL_PROVIDER_ENDPOINTS" in error


async def test_internal_private_http_endpoint_is_accepted_when_enabled(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	assert await validate_api_base("http://10.0.0.5:8000/v1", is_internal=True) is None
	assert await validate_api_base("http://127.0.0.1:11434/v1", is_internal=True) is None


@pytest.mark.parametrize(
	"url",
	[
		"http://169.254.169.254/latest",
		"http://[fe80::1]/v1",
		"http://0.0.0.0:8000/v1",
		"http://224.0.0.1/v1",
		"http://[fd00:ec2::254]/latest",
		"http://[::ffff:169.254.169.254]/latest",  # IPv4-mapped metadata address
		"http://[::ffff:0.0.0.0]/v1",
		"http://2852039166/latest",  # 169.254.169.254 written as one decimal number
	],
)
async def test_internal_endpoints_can_never_reach_metadata_or_link_local(monkeypatch, url):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	assert await validate_api_base(url, is_internal=True) is not None


async def test_internal_endpoint_still_rejects_credentials_in_the_url(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	assert await validate_api_base("http://u:p@10.0.0.5/v1", is_internal=True) is not None


async def test_unresolvable_host_is_rejected(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	assert await validate_api_base("http://no-such-host.invalid/v1", is_internal=True) is not None
