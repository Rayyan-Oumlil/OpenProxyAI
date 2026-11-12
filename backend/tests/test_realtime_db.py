"""WS /v1/realtime end to end: the real app served over a real socket, the real database, and a fake provider that records what it receives."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
import uvicorn
import websockets
from sqlalchemy import update
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.config import settings
from app.database import SystemSessionLocal, org_scoped_session
from app.main import app
from app.models.api_key import ApiKey
from app.routes import realtime as rt
from app.services import auth_service as auth
from app.services.llm_service import ProviderKeyCandidate, llm_service
from app.services.policy_service import PolicyConfig, policy_store
from tests.conftest import FakeRedis
from tests.db_helpers import remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

MODEL = "openai/gpt-4o-realtime-preview"
DONE = {"type": "response.done", "response": {"id": "resp_1", "status": "completed", "usage": {"input_tokens": 100, "output_tokens": 50}}}


@pytest.fixture
async def provider(monkeypatch):
	"""A fake realtime provider on a local port: records the headers it was opened with and every event it receives."""
	seen = SimpleNamespace(headers=[], received=[], opened=0)

	async def handler(connection):
		seen.opened += 1
		seen.headers.append(dict(connection.request.headers))
		await connection.send(json.dumps({"type": "session.created"}))
		async for raw in connection:
			event = json.loads(raw)
			seen.received.append(event)
			if event["type"] == "response.create":
				await connection.send(json.dumps({"type": "response.audio.delta", "delta": "AAAA"}))
				await connection.send(json.dumps(DONE))

	server = await websockets.serve(handler, "127.0.0.1", 0)
	port = server.sockets[0].getsockname()[1]
	monkeypatch.setattr(settings, "REALTIME_UPSTREAM_URL", f"ws://127.0.0.1:{port}/v1/realtime")

	async def keys(*_a, **_k):
		return [ProviderKeyCandidate(None, "sk-provider-secret", None)]

	monkeypatch.setattr(llm_service, "_select_provider_keys", keys)
	yield seen
	server.close()
	await server.wait_closed()


@pytest.fixture
async def logs(monkeypatch):
	rows = []

	async def log_request(**kwargs):
		rows.append(kwargs)

	monkeypatch.setattr(rt.ls, "log_request", log_request)
	return rows


@pytest.fixture
async def gateway():
	app.state.redis = FakeRedis()
	server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, lifespan="off", log_level="warning"))
	task = asyncio.create_task(server.serve())
	while not server.started:
		await asyncio.sleep(0.01)
	port = server.servers[0].sockets[0].getsockname()[1]
	yield SimpleNamespace(url=f"ws://127.0.0.1:{port}/v1/realtime", redis=app.state.redis)
	server.should_exit = True
	await task


@pytest.fixture
async def key(tenants):
	async with org_scoped_session(tenants.a) as db:
		model, full = await auth.create_api_key(db=db, user_id=tenants.user_a.id, org_id=tenants.a, name="rt", permissions=["proxy:llm"], expires_at=None)
	return SimpleNamespace(id=model.id, full=full)


async def configure(org_id, **policy):
	async with org_scoped_session(org_id) as db:
		await policy_store.save(org_id, PolicyConfig(**policy), db, FakeRedis())


def say(text):
	return json.dumps({"type": "conversation.item.create", "item": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}})


async def connect(gateway, key, model=MODEL, **kw):
	kw.setdefault("additional_headers", {"Authorization": f"Bearer {key.full}"})
	return await websockets.connect(f"{gateway.url}?model={model}", **kw)


async def closed_with(socket):
	with pytest.raises(ConnectionClosed):
		await asyncio.wait_for(socket.recv(), 5)
	return socket.close_code, socket.close_reason


async def test_a_session_relays_both_ways_bills_the_response_and_uses_the_orgs_key_not_the_callers(tenants, key, gateway, provider, logs):
	async with await connect(gateway, key) as ws:
		assert json.loads(await ws.recv())["type"] == "session.created"
		await ws.send(say("hello"))
		await ws.send(json.dumps({"type": "response.create"}))
		types = [json.loads(await asyncio.wait_for(ws.recv(), 5))["type"] for _ in range(2)]
	assert types == ["response.audio.delta", "response.done"]
	assert [e["type"] for e in provider.received] == ["conversation.item.create", "response.create"]
	assert provider.headers[0]["authorization"] == "Bearer sk-provider-secret" and key.full not in json.dumps(provider.headers)
	await asyncio.sleep(0.1)
	billed = [row for row in logs if row["status_code"] == 200]
	assert len(billed) == 1
	row = billed[0]
	assert (row["prompt_tokens"], row["completion_tokens"], row["org_id"], row["provider"]) == (100, 50, tenants.a, "openai")
	assert row["request_metadata"]["modality"] == "realtime" and row["cost_usd"] > 0


async def test_text_the_policy_blocks_never_reaches_the_provider_and_is_logged(tenants, key, gateway, provider, logs):
	await configure(tenants.a, enforcement_mode="enforce", blocked_keywords=["falcon"], pii_detection_enabled=False)
	async with await connect(gateway, key) as ws:
		await ws.recv()
		await ws.send(say("Project Falcon is confidential"))
		error = json.loads(await asyncio.wait_for(ws.recv(), 5))
		await ws.send(say("the weather is nice"))
		await asyncio.sleep(0.3)
	assert error["type"] == "error" and error["error"]["code"] == "policy_violation"
	assert [json.dumps(e) for e in provider.received if "alcon" in json.dumps(e)] == []
	assert len(provider.received) == 1
	assert [r["status_code"] for r in logs if r["status_code"] != 200] == [446]


@pytest.mark.parametrize("headers", [None, {"Authorization": "Bearer opai_not_a_real_key"}, {"Authorization": "Bearer sk-openai-style"}, {"Authorization": "Basic abc"}])
async def test_a_connection_without_a_valid_key_is_refused_before_it_opens(tenants, key, gateway, provider, headers):
	with pytest.raises(InvalidStatus) as caught:
		await websockets.connect(f"{gateway.url}?model={MODEL}", additional_headers=headers)
	assert caught.value.response.status_code == 403 and provider.opened == 0


async def test_a_key_in_the_url_is_not_a_credential(tenants, key, gateway, provider):
	with pytest.raises(InvalidStatus):
		await websockets.connect(f"{gateway.url}?model={MODEL}&api_key={key.full}")
	assert provider.opened == 0


async def test_a_browser_can_authenticate_with_a_subprotocol(tenants, key, gateway, provider, logs):
	async with websockets.connect(f"{gateway.url}?model={MODEL}", subprotocols=["realtime", f"openai-insecure-api-key.{key.full}"]) as ws:
		assert ws.subprotocol == "realtime" and json.loads(await ws.recv())["type"] == "session.created"


@pytest.mark.parametrize("model,reason", [("anthropic/claude-3-5-sonnet", "only_openai_is_supported"), ("no-slash", "model_must_be_provider_slash_name")])
async def test_other_providers_and_malformed_models_are_closed_with_the_reason(tenants, key, gateway, provider, model, reason):
	async with await connect(gateway, key, model=model) as ws:
		assert await closed_with(ws) == (1008, reason)
	assert provider.opened == 0


async def test_a_model_the_policy_does_not_allow_is_refused_and_logged(tenants, key, gateway, provider, logs):
	await configure(tenants.a, enforcement_mode="enforce", allowed_models=["openai/gpt-4o-mini"], pii_detection_enabled=False)
	async with await connect(gateway, key) as ws:
		code, reason = await closed_with(ws)
	assert code == 1008 and reason.startswith("policy_blocked") and provider.opened == 0 and [r["status_code"] for r in logs] == [446]


async def test_an_org_that_enforces_response_guardrails_cannot_use_realtime(tenants, key, gateway, provider, logs):
	await configure(tenants.a, enforcement_mode="enforce", response_guardrails_enabled=True, pii_detection_enabled=False)
	async with await connect(gateway, key) as ws:
		assert await closed_with(ws) == (1008, "response_guardrails_not_supported_in_realtime")
	assert provider.opened == 0


async def test_the_gateways_own_limits_stop_a_response_but_not_the_session(tenants, key, gateway, provider, logs, monkeypatch):
	monkeypatch.setattr(settings, "DEFAULT_RATE_LIMIT_RPM", 2)  # the connection takes one, the first response the second
	async with await connect(gateway, key) as ws:
		await ws.recv()
		await ws.send(json.dumps({"type": "response.create"}))
		assert json.loads(await asyncio.wait_for(ws.recv(), 5))["type"] == "response.audio.delta"
		await ws.recv()
		await ws.send(json.dumps({"type": "response.create", "event_id": "e2"}))
		error = json.loads(await asyncio.wait_for(ws.recv(), 5))
	assert error["error"]["code"] == "limit_exceeded" and "rate_limited" in error["error"]["message"]
	assert [e["type"] for e in provider.received] == ["response.create"]


async def test_a_key_revoked_while_a_session_is_open_ends_it(tenants, key, gateway, provider, monkeypatch):
	monkeypatch.setattr(settings, "REALTIME_CHECK_SECONDS", 0.2)
	async with await connect(gateway, key) as ws:
		await ws.recv()
		async with SystemSessionLocal() as session:
			await session.execute(update(ApiKey).where(ApiKey.id == key.id).values(is_active=False))
			await session.commit()
		assert await closed_with(ws) == (1008, "credentials_no_longer_valid")


async def test_a_policy_tightened_while_a_session_is_open_applies_to_the_next_message(tenants, key, gateway, provider, monkeypatch):
	monkeypatch.setattr(settings, "REALTIME_CHECK_SECONDS", 0.2)
	async with await connect(gateway, key) as ws:
		await ws.recv()
		await configure(tenants.a, enforcement_mode="enforce", blocked_keywords=["falcon"], pii_detection_enabled=False)
		await gateway.redis.delete(f"policy:config:{tenants.a}")  # saving through another process leaves this process's cached copy until it expires
		reply = None
		for _ in range(30):
			await asyncio.sleep(0.1)
			await ws.send(say("falcon"))
			try:
				reply = json.loads(await asyncio.wait_for(ws.recv(), 0.3))
			except TimeoutError:
				continue
			break
	assert reply is not None and reply["type"] == "error"


async def test_the_session_cap_is_per_org_and_freed_when_a_session_ends(tenants, key, gateway, provider, monkeypatch):
	monkeypatch.setattr(settings, "REALTIME_MAX_SESSIONS_PER_ORG", 1)
	async with await connect(gateway, key) as first:
		await first.recv()
		async with await connect(gateway, key) as second:
			assert await closed_with(second) == (1008, "too_many_realtime_sessions")
	await asyncio.sleep(0.3)
	async with await connect(gateway, key) as again:
		assert json.loads(await again.recv())["type"] == "session.created"


async def test_when_the_provider_is_down_the_client_is_told_and_no_session_is_counted(tenants, key, gateway, provider, logs, monkeypatch):
	async def refuse(*_a, **_k):
		raise OSError("connection refused: key sk-provider-secret")

	monkeypatch.setattr(rt, "open_upstream", refuse)
	async with await connect(gateway, key) as ws:
		code, reason = await closed_with(ws)
	assert (code, reason) == (1008, "provider_unavailable") and "sk-provider" not in reason
	assert [r["status_code"] for r in logs] == [502] and int(await gateway.redis.get(f"rt:sessions:{tenants.a}") or 0) == 0
