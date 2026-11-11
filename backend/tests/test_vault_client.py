"""Reading provider keys from Vault: path isolation, authentication, TLS, caching and failure behaviour (Phase 5, slice 5.10)."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.config import settings
from app.services import vault_client as vc
from app.services.key_secrets import display_label, resolve_secret

ORG, OTHER_ORG = uuid.uuid4(), uuid.uuid4()
SECRET = "sk-live-from-vault-123456"


@pytest.fixture(autouse=True)
def vault_settings(monkeypatch):
	for name, value in dict(
		VAULT_ADDR="https://vault.example:8200", VAULT_TOKEN="s.operator-token", VAULT_ROLE_ID="", VAULT_SECRET_ID="", VAULT_NAMESPACE="",
		VAULT_KV_MOUNT="secret", VAULT_PATH_PREFIX="openproxyai/{org_id}/", VAULT_CACHE_SECONDS=60, VAULT_ALLOW_INSECURE_HTTP=False,
	).items():
		monkeypatch.setattr(settings, name, value)


def fake_vault(secrets=None, *, status=200, approle_ttl=3600, record=None):
	"""A Vault that serves KV v2 reads and AppRole logins, and records every request it receives."""
	secrets = secrets if secrets is not None else {f"openproxyai/{ORG}/openai": {"api_key": SECRET, "other": "x"}}
	record = record if record is not None else []

	def handler(request: httpx.Request) -> httpx.Response:
		record.append(request)
		if request.url.path == "/v1/auth/approle/login":
			body = json.loads(request.content)
			if body != {"role_id": "role", "secret_id": "sid"}:
				return httpx.Response(400, json={"errors": ["bad login"]})
			return httpx.Response(200, json={"auth": {"client_token": "s.approle-token", "lease_duration": approle_ttl}})
		prefix = "/v1/secret/data/"
		if request.url.path.startswith(prefix):
			if status != 200:
				return httpx.Response(status, json={"errors": ["permission denied: secret-detail-the-client-must-not-repeat"]})
			path = request.url.path[len(prefix):]
			if path in secrets:
				return httpx.Response(200, json={"data": {"data": secrets[path], "metadata": {"version": 3}}})
			return httpx.Response(404, json={"errors": []})
		return httpx.Response(404)

	return httpx.MockTransport(handler), record


def client(**kwargs):
	transport, record = fake_vault(**kwargs)
	return vc.VaultClient(transport=transport), record


# -- paths: one org must not reach another's secrets ------------------------------------------------


@pytest.mark.parametrize("path", [
	f"openproxyai/{OTHER_ORG}/openai",  # another org's folder
	"openproxyai/openai", "secret/other-team/db-password", f"openproxyai/{ORG}",  # not inside, or the folder itself
	f"openproxyai/{ORG}/../{OTHER_ORG}/openai", f"openproxyai/{ORG}/..", "/etc/passwd", f"/openproxyai/{ORG}/openai",
	f"openproxyai/{ORG}//openai", f"openproxyai/{ORG}/openai?x=1", f"openproxyai/{ORG}/open ai", f"openproxyai/{ORG}/openai%2f..",
	f"openproxyai/{ORG}/openai\n", "", f"openproxyai/{ORG}/" + "a" * 600,
])
def test_a_path_outside_the_orgs_folder_or_with_odd_characters_is_refused(path):
	with pytest.raises(ValueError):
		vc.validate_path(ORG, path)


@pytest.mark.parametrize("field", ["", "a b", "a/b", "a;b", "x" * 101])
def test_a_field_name_must_be_plain(field):
	with pytest.raises(ValueError):
		vc.validate_path(ORG, f"openproxyai/{ORG}/openai", field)


def test_paths_inside_the_orgs_folder_are_accepted_including_subfolders():
	vc.validate_path(ORG, f"openproxyai/{ORG}/openai")
	vc.validate_path(ORG, f"openproxyai/{ORG}/team-a/prod/openai.key", "api_key")


def test_the_prefix_is_configurable_per_deployment(monkeypatch):
	monkeypatch.setattr(settings, "VAULT_PATH_PREFIX", "tenants/{org_id}/llm/")
	vc.validate_path(ORG, f"tenants/{ORG}/llm/openai")
	with pytest.raises(ValueError):
		vc.validate_path(ORG, f"openproxyai/{ORG}/openai")


async def test_the_path_is_checked_on_every_read_not_only_when_the_key_was_created():
	vault, record = client()
	with pytest.raises(vc.VaultError):
		await vault.read(ORG, f"openproxyai/{OTHER_ORG}/openai")
	assert record == []  # Vault was never asked


async def test_another_orgs_cached_secret_is_not_served_to_this_org():
	path = f"openproxyai/{ORG}/openai"
	vault, _ = client()
	assert await vault.read(ORG, path) == SECRET
	with pytest.raises(vc.VaultError):
		await vault.read(OTHER_ORG, path)  # the cache is keyed by path, and the path is not inside the other org's folder


# -- reading ----------------------------------------------------------------------------------------


async def test_a_secret_is_read_from_kv_v2_with_the_operators_token():
	vault, record = client()
	assert await vault.read(ORG, f"openproxyai/{ORG}/openai") == SECRET
	assert record[0].headers["x-vault-token"] == "s.operator-token" and record[0].method == "GET"
	assert record[0].url.path == f"/v1/secret/data/openproxyai/{ORG}/openai"


async def test_a_named_field_is_read_and_the_default_is_api_key():
	vault, _ = client()
	assert await vault.read(ORG, f"openproxyai/{ORG}/openai", "other") == "x"


async def test_a_namespace_and_a_different_mount_are_honoured(monkeypatch):
	monkeypatch.setattr(settings, "VAULT_NAMESPACE", "team-ns")
	monkeypatch.setattr(settings, "VAULT_KV_MOUNT", "kv")
	seen = []

	def handler(request):
		seen.append(request)
		return httpx.Response(200, json={"data": {"data": {"api_key": SECRET}}})

	await vc.VaultClient(transport=httpx.MockTransport(handler)).read(ORG, f"openproxyai/{ORG}/openai")
	assert seen[0].headers["x-vault-namespace"] == "team-ns" and seen[0].url.path.startswith("/v1/kv/data/")


async def test_approle_logs_in_once_and_reuses_the_token_until_it_expires(monkeypatch):
	monkeypatch.setattr(settings, "VAULT_TOKEN", "")
	monkeypatch.setattr(settings, "VAULT_ROLE_ID", "role")
	monkeypatch.setattr(settings, "VAULT_SECRET_ID", "sid")
	monkeypatch.setattr(settings, "VAULT_CACHE_SECONDS", 0)  # no secret cache, so each read goes to Vault
	vault, record = client()
	await vault.read(ORG, f"openproxyai/{ORG}/openai")
	await vault.read(ORG, f"openproxyai/{ORG}/openai")
	logins = [r for r in record if r.url.path == "/v1/auth/approle/login"]
	reads = [r for r in record if r.url.path.startswith("/v1/secret/data/")]
	assert len(logins) == 1 and len(reads) == 2 and {r.headers["x-vault-token"] for r in reads} == {"s.approle-token"}


async def test_an_expired_approle_token_is_replaced(monkeypatch):
	monkeypatch.setattr(settings, "VAULT_TOKEN", "")
	monkeypatch.setattr(settings, "VAULT_ROLE_ID", "role")
	monkeypatch.setattr(settings, "VAULT_SECRET_ID", "sid")
	monkeypatch.setattr(settings, "VAULT_CACHE_SECONDS", 0)
	vault, record = client(approle_ttl=10)  # shorter than the refresh margin: already expired when stored
	await vault.read(ORG, f"openproxyai/{ORG}/openai")
	await vault.read(ORG, f"openproxyai/{ORG}/openai")
	assert len([r for r in record if r.url.path == "/v1/auth/approle/login"]) == 2


async def test_a_rejected_approle_login_is_an_error_without_the_response_body(monkeypatch):
	monkeypatch.setattr(settings, "VAULT_TOKEN", "")
	monkeypatch.setattr(settings, "VAULT_ROLE_ID", "wrong")
	monkeypatch.setattr(settings, "VAULT_SECRET_ID", "wrong")
	vault, _ = client()
	with pytest.raises(vc.VaultError, match="AppRole login.*400") as caught:
		await vault.read(ORG, f"openproxyai/{ORG}/openai")
	assert "bad login" not in str(caught.value)


# -- the cache ---------------------------------------------------------------------------------------


async def test_a_secret_is_cached_and_a_rotated_one_is_picked_up_after_the_cache_expires(monkeypatch):
	path = f"openproxyai/{ORG}/openai"
	secrets = {path: {"api_key": "sk-old-value-000000"}}
	vault, record = client(secrets=secrets)
	assert await vault.read(ORG, path) == "sk-old-value-000000"
	secrets[path] = {"api_key": "sk-new-value-111111"}
	assert await vault.read(ORG, path) == "sk-old-value-000000" and len(record) == 1  # served from the cache
	monkeypatch.setattr(settings, "VAULT_CACHE_SECONDS", 0)
	vault.forget()
	assert await vault.read(ORG, path) == "sk-new-value-111111"


# -- failure: hard, specific and without leaking -----------------------------------------------------


@pytest.mark.parametrize("status", [403, 404, 500, 503])
async def test_vault_errors_are_vault_errors_that_carry_the_status_and_not_the_body(status):
	vault, _ = client(status=status)
	with pytest.raises(vc.VaultError, match=f"HTTP {status}") as caught:
		await vault.read(ORG, f"openproxyai/{ORG}/openai")
	assert "secret-detail" not in str(caught.value)


async def test_a_missing_secret_and_a_missing_field_are_errors():
	vault, _ = client(secrets={})
	with pytest.raises(vc.VaultError, match="HTTP 404"):
		await vault.read(ORG, f"openproxyai/{ORG}/openai")
	vault, _ = client()
	with pytest.raises(vc.VaultError, match="no 'nope' field"):
		await vault.read(ORG, f"openproxyai/{ORG}/openai", "nope")


async def test_an_empty_or_non_string_value_is_an_error_not_an_empty_key():
	for bad in ("", None, 12345, ["x"]):
		vault, _ = client(secrets={f"openproxyai/{ORG}/openai": {"api_key": bad}})
		with pytest.raises(vc.VaultError):
			await vault.read(ORG, f"openproxyai/{ORG}/openai")


async def test_an_unreachable_vault_is_an_error_naming_the_exception_class_only():
	def handler(request):
		raise httpx.ConnectError("connection refused to https://vault.example:8200 with token s.operator-token")

	with pytest.raises(vc.VaultError) as caught:
		await vc.VaultClient(transport=httpx.MockTransport(handler)).read(ORG, f"openproxyai/{ORG}/openai")
	assert "ConnectError" in str(caught.value) and "s.operator-token" not in str(caught.value) and "vault.example" not in str(caught.value)


async def test_a_redirect_is_not_followed_so_the_token_cannot_be_sent_elsewhere():
	seen = []

	def handler(request):
		seen.append(str(request.url))
		return httpx.Response(307, headers={"location": "https://evil.example/steal"})

	with pytest.raises(vc.VaultError, match="HTTP 307"):
		await vc.VaultClient(transport=httpx.MockTransport(handler)).read(ORG, f"openproxyai/{ORG}/openai")
	assert seen == [f"https://vault.example:8200/v1/secret/data/openproxyai/{ORG}/openai"]


async def test_plain_http_is_refused_unless_the_operator_allows_it(monkeypatch):
	monkeypatch.setattr(settings, "VAULT_ADDR", "http://vault.internal:8200")
	vault, record = client()
	with pytest.raises(vc.VaultError, match="https"):
		await vault.read(ORG, f"openproxyai/{ORG}/openai")
	assert record == []
	monkeypatch.setattr(settings, "VAULT_ALLOW_INSECURE_HTTP", True)
	assert await vault.read(ORG, f"openproxyai/{ORG}/openai") == SECRET


async def test_an_address_that_is_not_a_url_is_refused(monkeypatch):
	monkeypatch.setattr(settings, "VAULT_ADDR", "file:///etc/passwd")
	with pytest.raises(vc.VaultError):
		await client()[0].read(ORG, f"openproxyai/{ORG}/openai")


async def test_without_configuration_reading_says_so_and_configured_is_false(monkeypatch):
	monkeypatch.setattr(settings, "VAULT_ADDR", "")
	assert vc.configured() is False
	with pytest.raises(vc.VaultNotConfigured):
		await client()[0].read(ORG, f"openproxyai/{ORG}/openai")
	monkeypatch.setattr(settings, "VAULT_ADDR", "https://v")
	monkeypatch.setattr(settings, "VAULT_TOKEN", "")
	assert vc.configured() is False  # an address with no credential is not usable


# -- the resolver ------------------------------------------------------------------------------------


def key(**fields):
	return SimpleNamespace(**{"org_id": ORG, "secret_source": "local", "api_key_encrypted": None, "vault_path": None, "vault_field": None, **fields})


async def test_a_stored_key_is_decrypted_and_a_vault_key_is_read_from_vault(monkeypatch):
	from app.services.crypto_service import encrypt

	assert await resolve_secret(key(api_key_encrypted=encrypt("sk-stored-123456"))) == "sk-stored-123456"
	transport, _ = fake_vault()
	monkeypatch.setattr(vc, "vault_client", vc.VaultClient(transport=transport))
	import app.services.key_secrets as ks

	monkeypatch.setattr(ks, "vault_client", vc.vault_client)
	assert await resolve_secret(key(secret_source="vault", vault_path=f"openproxyai/{ORG}/openai")) == SECRET


async def test_a_vault_key_never_falls_back_to_a_stored_value():
	"""Even if some ciphertext is somehow present, a Vault key is read from Vault only; a Vault failure stays a failure."""
	from app.services.crypto_service import encrypt

	broken = key(secret_source="vault", vault_path=f"openproxyai/{OTHER_ORG}/x", api_key_encrypted=encrypt("sk-stale-000000"))
	with pytest.raises(vc.VaultError):
		await resolve_secret(broken)


def test_the_console_label_for_a_vault_key_is_its_place_in_vault_never_a_value():
	assert display_label(key(secret_source="vault", vault_path=f"openproxyai/{ORG}/openai")) == f"vault:openproxyai/{ORG}/openai"
	assert display_label(key()) == ""
