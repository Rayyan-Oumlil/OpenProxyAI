"""Live LLM integration tests (opt-in only).

These tests call real providers and are skipped by default.
Enable with:
	- OPENPROXYAI_RUN_LIVE_LLM_TESTS=true
	- OPENPROXYAI_LIVE_OPENAI_API_KEY=<your_key>
"""

import os
import uuid

import pytest

from app.config import settings


def _live_enabled() -> bool:
	return os.getenv("OPENPROXYAI_RUN_LIVE_LLM_TESTS", "false").lower() == "true"


def _live_openai_key() -> str:
	return os.getenv("OPENPROXYAI_LIVE_OPENAI_API_KEY", "").strip()


pytestmark = [
	pytest.mark.integration,
	pytest.mark.skipif(not _live_enabled(), reason="Live LLM tests disabled"),
]


def _register_and_create_proxy_key(client) -> str:
	email = f"live_{uuid.uuid4().hex[:10]}@example.com"
	password = "Passw0rd!"
	register = client.post(
		"/api/v1/auth/register",
		json={"email": email, "password": password, "name": "Live Tester", "org_name": "Live Org"},
	)
	assert register.status_code == 200, register.text
	access_token = register.json()["access_token"]

	create_key = client.post(
		"/api/v1/api-keys",
		headers={"Authorization": f"Bearer {access_token}"},
		json={"name": "live-proxy-key"},
	)
	assert create_key.status_code == 201, create_key.text
	return create_key.json()["key"]


def test_live_chat_completion_non_streaming(client):
	key = _live_openai_key()
	if not key:
		pytest.skip("OPENPROXYAI_LIVE_OPENAI_API_KEY not set")

	settings.OPENAI_API_KEY = key
	proxy_key = _register_and_create_proxy_key(client)

	response = client.post(
		"/v1/chat/completions",
		headers={"Authorization": f"Bearer {proxy_key}"},
		json={
			"model": "openai/gpt-4o-mini",
			"messages": [{"role": "user", "content": "Reply with exactly: OK"}],
			"max_tokens": 20,
		},
	)

	assert response.status_code == 200, response.text
	body = response.json()
	assert body.get("object") == "chat.completion"
	assert "choices" in body and len(body["choices"]) > 0
	assert "x-openproxyai-provider" in response.headers
	assert "x-openproxyai-cost-usd" in response.headers


def test_live_embeddings(client):
	key = _live_openai_key()
	if not key:
		pytest.skip("OPENPROXYAI_LIVE_OPENAI_API_KEY not set")

	settings.OPENAI_API_KEY = key
	proxy_key = _register_and_create_proxy_key(client)

	response = client.post(
		"/v1/embeddings",
		headers={"Authorization": f"Bearer {proxy_key}"},
		json={"model": "openai/text-embedding-3-small", "input": "OpenProxyAI integration test"},
	)

	assert response.status_code == 200, response.text
	body = response.json()
	assert body.get("object") == "list"
	assert "data" in body and len(body["data"]) > 0
	assert body["data"][0].get("object") == "embedding"
	assert "x-openproxyai-provider" in response.headers
	assert "x-openproxyai-cost-usd" in response.headers
