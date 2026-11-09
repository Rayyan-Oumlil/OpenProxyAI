"""The connection guard for custom provider endpoints: where the gateway may actually connect, per request."""

from __future__ import annotations

import asyncio
import datetime
import ssl
from pathlib import Path

import httpx
import pytest

from app.config import settings
from tests.fakes.redirecting_openai import Servers
from app.services.provider_client import EgressRefused, GuardedTransport, ProviderEndpoint, guarded_http_client, openai_client_for


# ── unit: the transport with a recording inner transport and a scripted resolver ──────────────────────────────


class Recorder(httpx.AsyncBaseTransport):
	def __init__(self):
		self.requests: list[httpx.Request] = []

	async def handle_async_request(self, request):
		self.requests.append(request)
		return httpx.Response(200, json={"ok": True})


def scripted(*answers: list[str]):
	"""A resolver that returns each scripted answer in turn (the last one repeats) and counts its calls."""
	calls = []

	async def resolve(host, port):
		calls.append((host, port))
		return list(answers[min(len(calls) - 1, len(answers) - 1)])

	resolve.calls = calls
	return resolve


async def send(transport, url="https://models.example.com/v1/chat/completions"):
	async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
		return await client.post(url, json={"x": 1})


@pytest.fixture(autouse=True)
def _internal_off(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", False)


async def test_it_connects_to_the_address_it_validated_and_keeps_the_hostname_for_the_server_and_tls():
	inner, resolve = Recorder(), scripted(["8.8.8.8"])
	response = await send(GuardedTransport(internal=False, inner=inner, resolver=resolve))

	assert response.status_code == 200
	[request] = inner.requests
	assert request.url.host == "8.8.8.8" and request.url.path == "/v1/chat/completions"  # connect to the validated IP
	assert request.headers["host"] == "models.example.com"  # the server still sees its own name
	assert request.extensions["sni_hostname"] == "models.example.com"  # and TLS is verified against the name, not the IP
	assert resolve.calls == [("models.example.com", 443)]


@pytest.mark.parametrize("answer", [["10.0.0.5"], ["127.0.0.1"], ["169.254.169.254"], ["100.64.0.1"], ["::1"]])
async def test_a_hostname_that_resolves_to_a_private_address_is_refused_for_an_external_endpoint(answer):
	inner = Recorder()
	with pytest.raises(EgressRefused):
		await send(GuardedTransport(internal=False, inner=inner, resolver=scripted(answer)))
	assert inner.requests == []


async def test_one_bad_address_among_good_ones_refuses_the_request():
	inner = Recorder()
	with pytest.raises(EgressRefused):
		await send(GuardedTransport(internal=False, inner=inner, resolver=scripted(["8.8.8.8", "10.0.0.5"])))
	assert inner.requests == []


async def test_an_unresolvable_host_is_refused():
	with pytest.raises(EgressRefused):
		await send(GuardedTransport(internal=False, inner=Recorder(), resolver=scripted([])))


async def test_dns_that_changes_between_requests_is_caught_on_the_request_that_changed():
	"""Rebinding: public when the endpoint was saved and checked, private later. Every request is judged on its own answer."""
	inner = Recorder()
	transport = GuardedTransport(internal=False, inner=inner, resolver=scripted(["8.8.8.8"], ["10.0.0.5"]))
	assert (await send(transport)).status_code == 200
	with pytest.raises(EgressRefused):
		await send(transport)
	assert [r.url.host for r in inner.requests] == ["8.8.8.8"]


async def test_each_request_resolves_once_so_there_is_no_gap_between_the_check_and_the_connection():
	inner, resolve = Recorder(), scripted(["8.8.8.8"], ["10.0.0.5"])
	await send(GuardedTransport(internal=False, inner=inner, resolver=resolve))
	assert len(resolve.calls) == 1 and inner.requests[0].url.host == "8.8.8.8"  # the second answer was never consulted


async def test_internal_endpoints_may_use_private_addresses_only_while_the_operator_allows_it(monkeypatch):
	transport = GuardedTransport(internal=True, inner=Recorder(), resolver=scripted(["10.0.0.5"]))
	with pytest.raises(EgressRefused):  # the operator switch is off
		await send(transport, "http://vllm.internal:8000/v1/chat/completions")
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	assert (await send(transport, "http://vllm.internal:8000/v1/chat/completions")).status_code == 200
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", False)  # switched off again while the client lives on
	with pytest.raises(EgressRefused):
		await send(transport, "http://vllm.internal:8000/v1/chat/completions")


@pytest.mark.parametrize("address", ["169.254.169.254", "fd00:ec2::254", "0.0.0.0", "::ffff:169.254.169.254"])
async def test_cloud_metadata_is_unreachable_even_for_an_internal_endpoint(monkeypatch, address):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	with pytest.raises(EgressRefused):
		await send(GuardedTransport(internal=True, inner=Recorder(), resolver=scripted([address])))


async def test_an_ip_literal_needs_no_lookup_and_ipv6_is_addressed_correctly(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	inner, resolve = Recorder(), scripted(["203.0.113.9"])
	await send(GuardedTransport(internal=True, inner=inner, resolver=resolve), "http://[::1]:8000/v1/models")
	assert resolve.calls == [] and inner.requests[0].url.host == "::1" and inner.requests[0].url.port == 8000
	with pytest.raises(EgressRefused):
		await send(GuardedTransport(internal=False, inner=Recorder(), resolver=resolve), "https://10.0.0.5/v1/models")


def test_a_refusal_is_a_transport_error_so_http_libraries_treat_it_as_a_connection_failure():
	assert issubclass(EgressRefused, httpx.TransportError)


# ── real sockets: redirects, LiteLLM, TLS ────────────────────────────────────────────────────────────────────


@pytest.fixture
def servers(monkeypatch):
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)  # the servers are on loopback
	running = Servers()
	yield running
	running.close()


async def test_a_redirect_from_a_validated_endpoint_is_not_followed(servers):
	async with guarded_http_client(internal=True) as client:
		response = await client.post(f"{servers.redirector_base}/chat/completions", json={"prompt": "secret"})
	assert response.status_code == 307
	assert servers.hits == {"target": 0, "redirector": 1}  # the request, with its body, never went where the redirect pointed


async def test_litellm_does_not_follow_a_redirect_when_it_uses_the_guarded_client(servers):
	import litellm

	endpoint = ProviderEndpoint(api_base=servers.redirector_base, is_internal=True)
	with pytest.raises(Exception):  # noqa: B017  (LiteLLM wraps the provider's status error in its own types)
		await litellm.acompletion(
			model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "secret"}], api_key="sk-test", api_base=endpoint.api_base,
			client=openai_client_for("sk-test", endpoint), num_retries=0, timeout=10,
		)
	assert servers.hits == {"target": 0, "redirector": 1}


async def test_litellm_reaches_a_direct_endpoint_through_the_guarded_client(servers):
	import litellm

	endpoint = ProviderEndpoint(api_base=servers.target_base, is_internal=True)
	reply = await litellm.acompletion(
		model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "hi"}], api_key="sk-test", api_base=endpoint.api_base,
		client=openai_client_for("sk-test", endpoint), num_retries=0, timeout=10,
	)
	assert reply.choices[0].message.content == "answer" and servers.hits["target"] == 1


def test_clients_are_reused_per_key_endpoint_and_event_loop():
	endpoint = ProviderEndpoint(api_base="https://models.example.com/v1", is_internal=False)

	async def clients():
		return openai_client_for("sk-a", endpoint), openai_client_for("sk-a", endpoint), openai_client_for("sk-b", endpoint)

	first, again, other_key = asyncio.run(clients())
	assert first is again and first is not other_key
	assert asyncio.run(clients())[0] is not first  # a client belongs to the event loop that made it


# ── real TLS: the certificate is checked against the hostname even though the connection goes to an IP ─────────────


def make_certificate(directory: Path, name: str, issuer_key=None, issuer_name=None):
	from cryptography import x509
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import rsa
	from cryptography.x509.oid import NameOID

	key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
	now = datetime.datetime.now(datetime.UTC)
	builder = (
		x509.CertificateBuilder().subject_name(subject).issuer_name(issuer_name or subject).public_key(key.public_key())
		.serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=1))
	)
	if issuer_key is None:
		builder = builder.add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
	else:
		builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
	cert = builder.sign(issuer_key or key, hashes.SHA256())
	cert_path, key_path = directory / f"{name}.crt", directory / f"{name}.key"
	cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
	key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
	return cert_path, key_path, key, subject


@pytest.fixture
def tls_server(tmp_path, monkeypatch):
	"""An HTTPS server whose certificate (issued by a private CA) is valid for 'models.test' only."""
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	ca_cert, _, ca_key, ca_name = make_certificate(tmp_path, "test-ca")
	server_cert, server_key, _, _ = make_certificate(tmp_path, "models.test", issuer_key=ca_key, issuer_name=ca_name)
	context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
	context.load_cert_chain(server_cert, server_key)
	running = Servers(tls_context=context)
	yield running, ssl.create_default_context(cafile=str(ca_cert))
	running.close()


async def test_tls_is_verified_against_the_hostname_while_connecting_to_the_pinned_address(tls_server):
	running, trust = tls_server
	port = running.target.server_port

	async def resolve(host, port_):
		return ["127.0.0.1"]

	async with guarded_http_client(internal=True, verify=trust, resolver=resolve) as client:
		ok = await client.post(f"https://models.test:{port}/v1/chat/completions", json={})
		assert ok.status_code == 200 and running.hits["target"] == 1
		# Same server, same IP, but a name the certificate was not issued for: verification must fail.
		with pytest.raises(httpx.ConnectError):
			await client.post(f"https://other.test:{port}/v1/chat/completions", json={})
	assert running.hits["target"] == 1
