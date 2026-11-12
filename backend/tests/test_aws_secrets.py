"""AWS Secrets Manager provider keys: name isolation, reading, caching and failure behaviour (unit tests with botocore's own stubber)."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import boto3
import pytest
from botocore.stub import Stubber

from app.config import settings
from app.services import aws_secrets as aws
from app.services.key_secrets import display_label, resolve_secret

ORG, OTHER = uuid.uuid4(), uuid.uuid4()
NAME = f"openproxyai/{ORG}/openai"
SECRET = "sk-from-aws-1234567890"


@pytest.fixture(autouse=True)
def aws_settings(monkeypatch):
	for name, value in dict(AWS_SECRETS_ENABLED=True, AWS_SECRETS_REGION="us-east-1", AWS_SECRET_PREFIX="openproxyai/{org_id}/", AWS_SECRET_CACHE_SECONDS=60).items():
		monkeypatch.setattr(settings, name, value)


def client_with(*responses, errors=()):
	"""An AwsSecretsClient whose boto client is stubbed: each response is returned in order, each error raised in order."""
	boto = boto3.client("secretsmanager", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
	stubber = Stubber(boto)
	for secret in responses:
		stubber.add_response("get_secret_value", {"Name": "n", "SecretString": secret})
	for code in errors:
		stubber.add_client_error("get_secret_value", service_error_code=code, service_message="detail the client must not repeat")
	stubber.activate()
	return aws.AwsSecretsClient(client_factory=lambda: boto), stubber


@pytest.mark.parametrize("name", [
	f"openproxyai/{OTHER}/openai", "openproxyai/openai", "prod/db-password", f"openproxyai/{ORG}", f"openproxyai/{ORG}/../{OTHER}/openai", "/etc/passwd",
	f"arn:aws:secretsmanager:us-east-1:123456789012:secret:openproxyai/{ORG}/openai", "ARN:aws:secretsmanager:eu-west-1:1:secret:x", f"openproxyai/{ORG}//openai",
	f"openproxyai/{ORG}/open ai", f"openproxyai/{ORG}/openai\n", "", f"openproxyai/{ORG}/" + "a" * 600,
])
def test_a_name_outside_the_orgs_folder_or_an_arn_is_refused(name):
	with pytest.raises(ValueError):
		aws.validate_name(ORG, name)


def test_names_inside_the_orgs_folder_are_accepted():
	aws.validate_name(ORG, NAME)
	aws.validate_name(ORG, f"openproxyai/{ORG}/team-a/prod/openai.key+v2", "api_key")


@pytest.mark.parametrize("field", ["", "a b", "a/b", "x" * 101])
def test_a_field_must_be_plain(field):
	with pytest.raises(ValueError):
		aws.validate_name(ORG, NAME, field)


async def test_the_name_is_checked_on_every_read_and_aws_is_never_asked_for_a_foreign_one():
	client, stubber = client_with(SECRET)
	with pytest.raises(aws.AwsSecretError):
		await client.read(ORG, f"openproxyai/{OTHER}/openai")
	assert len(stubber._queue) == 1  # the one prepared response was not consumed: no call was made


async def test_a_plain_string_secret_is_the_key_and_a_json_secret_is_read_by_field():
	client, _ = client_with(SECRET)
	assert await client.read(ORG, NAME) == SECRET
	client, _ = client_with(json.dumps({"api_key": SECRET, "other": "x"}))
	assert await client.read(ORG, NAME) == SECRET
	client, _ = client_with(json.dumps({"api_key": SECRET, "other": "x"}))
	assert await client.read(ORG, NAME, "other") == "x"


async def test_a_missing_field_or_a_non_json_secret_asked_for_a_field_is_an_error():
	client, _ = client_with(json.dumps({"api_key": SECRET}))
	with pytest.raises(aws.AwsSecretError, match="no 'nope' field"):
		await client.read(ORG, NAME, "nope")
	client, _ = client_with(SECRET)
	with pytest.raises(aws.AwsSecretError, match="not JSON"):
		await client.read(ORG, NAME, "other")


async def test_an_empty_or_non_string_value_is_an_error_not_an_empty_key():
	for bad in (json.dumps({"api_key": ""}), json.dumps({"api_key": 5}), json.dumps({"api_key": None})):
		client, _ = client_with(bad)
		with pytest.raises(aws.AwsSecretError):
			await client.read(ORG, NAME)


async def test_a_secret_is_cached_and_read_again_after_the_cache_expires(monkeypatch):
	client, stubber = client_with("sk-old-value-000000", "sk-new-value-111111")
	assert await client.read(ORG, NAME) == "sk-old-value-000000"
	assert await client.read(ORG, NAME) == "sk-old-value-000000" and len(stubber._queue) == 1  # served from the cache
	monkeypatch.setattr(settings, "AWS_SECRET_CACHE_SECONDS", 0)
	client._secrets.clear()
	assert await client.read(ORG, NAME) == "sk-new-value-111111"


@pytest.mark.parametrize("code", ["ResourceNotFoundException", "AccessDeniedException", "DecryptionFailure", "InternalServiceError"])
async def test_aws_errors_carry_the_code_and_never_the_message(code):
	client, _ = client_with(errors=[code])
	with pytest.raises(aws.AwsSecretError, match=code) as caught:
		await client.read(ORG, NAME)
	assert "detail the client must not repeat" not in str(caught.value)


async def test_a_binary_secret_is_refused():
	boto = boto3.client("secretsmanager", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
	stubber = Stubber(boto)
	stubber.add_response("get_secret_value", {"Name": "n", "SecretBinary": b"\x00\x01"})
	stubber.activate()
	with pytest.raises(aws.AwsSecretError, match="no text value"):
		await aws.AwsSecretsClient(client_factory=lambda: boto).read(ORG, NAME)


async def test_a_network_failure_is_an_error_naming_the_exception_class_only():
	class Broken:
		def get_secret_value(self, **_k):
			raise ConnectionError("could not connect to secretsmanager.us-east-1.amazonaws.com with key AKIAEXAMPLE")

	with pytest.raises(aws.AwsSecretError) as caught:
		await aws.AwsSecretsClient(client_factory=Broken).read(ORG, NAME)
	assert "ConnectionError" in str(caught.value) and "AKIA" not in str(caught.value) and "amazonaws" not in str(caught.value)


async def test_reading_says_so_when_it_is_not_enabled(monkeypatch):
	monkeypatch.setattr(settings, "AWS_SECRETS_ENABLED", False)
	client, stubber = client_with(SECRET)
	with pytest.raises(aws.AwsSecretError, match="not enabled"):
		await client.read(ORG, NAME)
	assert len(stubber._queue) == 1


# -- the resolver ---------------------------------------------------------------------------------------


def key(**fields):
	return SimpleNamespace(**{"org_id": ORG, "secret_source": "aws", "api_key_encrypted": None, "vault_path": NAME, "vault_field": None, **fields})


async def test_an_aws_key_is_read_from_aws_and_never_falls_back_to_a_stored_or_vault_value(monkeypatch):
	import app.services.key_secrets as ks
	from app.services.crypto_service import encrypt

	client, _ = client_with(SECRET)
	monkeypatch.setattr(ks, "aws_secrets", client)
	assert await resolve_secret(key()) == SECRET
	broken, _ = client_with(errors=["AccessDeniedException"])
	monkeypatch.setattr(ks, "aws_secrets", broken)
	with pytest.raises(aws.AwsSecretError):
		await resolve_secret(key(api_key_encrypted=encrypt("sk-stale-0000000000")))  # stale ciphertext is ignored, not substituted


def test_the_console_label_names_the_source_and_never_a_value():
	assert display_label(key()) == f"aws:{NAME}"
	assert display_label(key(secret_source="local", vault_path=None)) == ""
