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
	assert await validate_api_base("https://8.8.8.8/v1", is_internal=False, provider="openai") is None


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
	assert await validate_api_base(url, is_internal=False, provider="openai") is not None


async def test_external_endpoint_is_refused_in_airgap_mode(monkeypatch):
	monkeypatch.setattr(settings, "AIRGAP_MODE", True)
	error = await validate_api_base("https://8.8.8.8/v1", is_internal=False, provider="openai")
	assert error and "air-gapped" in error


# ── internal endpoints (vLLM, Ollama, private gateways) ──────────────────────


async def test_internal_endpoints_are_off_unless_the_operator_enables_them():
	error = await validate_api_base("http://10.0.0.5:8000/v1", is_internal=True, provider="openai")
	assert error and "ALLOW_INTERNAL_PROVIDER_ENDPOINTS" in error


async def test_internal_private_http_endpoint_is_accepted_when_enabled(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	assert await validate_api_base("http://10.0.0.5:8000/v1", is_internal=True, provider="openai") is None
	assert await validate_api_base("http://127.0.0.1:11434/v1", is_internal=True, provider="openai") is None


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
	assert await validate_api_base(url, is_internal=True, provider="openai") is not None


async def test_internal_endpoint_still_rejects_credentials_in_the_url(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	assert await validate_api_base("http://u:p@10.0.0.5/v1", is_internal=True, provider="openai") is not None


async def test_unresolvable_host_is_rejected(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	assert await validate_api_base("http://no-such-host.invalid/v1", is_internal=True, provider="openai") is not None


# ── call-time re-check (a hostname can start resolving somewhere else after it was saved) ──


from types import SimpleNamespace  # noqa: E402

from app.utils import provider_endpoint  # noqa: E402
from app.utils.provider_endpoint import filter_allowed_endpoints  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_cache():
	provider_endpoint.clear_runtime_cache()


def _key(api_base, is_internal=False, provider="openai"):
	return SimpleNamespace(id=object(), api_base=api_base, is_internal=is_internal, provider=provider)


async def test_keys_without_a_custom_endpoint_are_never_checked():
	keys = [_key(None)]
	kept, dropped = await filter_allowed_endpoints(keys)
	assert kept == keys and dropped == 0


async def test_a_key_whose_endpoint_stopped_validating_is_dropped(monkeypatch):
	good, flipped = _key("https://8.8.8.8/v1"), _key("https://1.1.1.1/v1")
	kept, dropped = await filter_allowed_endpoints([good, flipped])
	assert kept == [good, flipped] and dropped == 0

	provider_endpoint.clear_runtime_cache()

	async def fake_resolve(url):
		return None if "1.1.1.1" in url else "8.8.8.8"  # the second host now points at a private address

	monkeypatch.setattr(provider_endpoint, "resolve_public_ip", fake_resolve)
	kept, dropped = await filter_allowed_endpoints([good, flipped])
	assert kept == [good] and dropped == 1


async def test_internal_keys_stop_working_when_the_operator_turns_the_switch_off(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	internal = _key("http://10.0.0.5:8000/v1", is_internal=True)
	assert (await filter_allowed_endpoints([internal]))[1] == 0

	provider_endpoint.clear_runtime_cache()
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", False)
	kept, dropped = await filter_allowed_endpoints([internal])
	assert kept == [] and dropped == 1


async def test_results_are_cached_so_every_request_does_not_resolve_dns(monkeypatch):
	calls = []

	async def counting(url):
		calls.append(url)
		return "8.8.8.8"

	monkeypatch.setattr(provider_endpoint, "resolve_public_ip", counting)
	key = _key("https://8.8.8.8/v1")
	for _ in range(5):
		await filter_allowed_endpoints([key])
	assert len(calls) == 1


# ── only OpenAI-compatible endpoints can be guarded ──────────────────────────


@pytest.mark.parametrize("provider", ["anthropic", "azure", "ollama", "gemini", "other"])
async def test_custom_endpoints_are_only_allowed_for_the_openai_provider(provider):
	error = await validate_api_base("https://8.8.8.8/v1", is_internal=False, provider=provider)
	assert error and "openai" in error


async def test_a_stored_custom_endpoint_on_another_provider_is_skipped_at_call_time():
	kept, dropped = await filter_allowed_endpoints([_key("https://8.8.8.8/v1", provider="anthropic")])
	assert kept == [] and dropped == 1
