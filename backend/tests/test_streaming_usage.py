"""Streaming requests must report usage and be billed even when the client disconnects (P0-5)."""
import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

from app.services import llm_service as llm_module
from tests.conftest import FakeDB
from tests.test_provider_fallback import _patch_common


class _Stream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _delta(text):
    return {"id": "x", "choices": [{"delta": {"content": text}, "finish_reason": None}]}


USAGE_CHUNK = {"id": "x", "choices": [], "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}}


async def _start(monkeypatch, fake_redis, upstream_chunks, **request_extra):
    _patch_common(monkeypatch)
    calls: list[dict] = []
    logs: list[dict] = []

    async def keys(*a, **kw):
        return [(None, "sk-test")]

    async def acompletion(**kw):
        calls.append(kw)
        return _Stream(upstream_chunks)

    async def record_log(**kw):
        logs.append(kw)

    monkeypatch.setattr(llm_module.llm_service, "_select_provider_keys", keys)
    monkeypatch.setattr(llm_module, "acompletion", acompletion)
    monkeypatch.setattr(llm_module, "log_request", record_log)

    background_tasks = BackgroundTasks()
    response = await llm_module.llm_service.chat_completion(
        request=llm_module.ChatCompletionRequest(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "hello there"}],
            stream=True,
            **request_extra,
        ),
        db=FakeDB(),
        redis=fake_redis,
        user=SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=None),
        api_key=SimpleNamespace(id=uuid4()),
        request_id=uuid4(),
        background_tasks=background_tasks,
        http_request=None,
    )
    return response, calls, logs, background_tasks


@pytest.mark.asyncio
async def test_include_usage_requested_and_merged_with_client_options(monkeypatch, fake_redis):
    response, calls, _, _ = await _start(
        monkeypatch, fake_redis, [_delta("a")], stream_options={"include_obfuscation": False}
    )
    [_ async for _ in response.body_iterator]

    assert calls[0]["stream_options"] == {"include_obfuscation": False, "include_usage": True}


@pytest.mark.asyncio
async def test_usage_chunk_hidden_unless_client_asked_for_it(monkeypatch, fake_redis):
    response, _, _, _ = await _start(monkeypatch, fake_redis, [_delta("a"), USAGE_CHUNK])
    body = "".join([c async for c in response.body_iterator])
    assert '"usage"' not in body

    response, _, _, _ = await _start(
        monkeypatch, fake_redis, [_delta("a"), USAGE_CHUNK], stream_options={"include_usage": True}
    )
    body = "".join([c async for c in response.body_iterator])
    assert '"usage"' in body


@pytest.mark.asyncio
async def test_completed_stream_logs_provider_usage(monkeypatch, fake_redis):
    response, _, logs, background_tasks = await _start(monkeypatch, fake_redis, [_delta("a"), USAGE_CHUNK])
    [_ async for _ in response.body_iterator]
    await background_tasks()

    assert len(logs) == 1
    assert (logs[0]["status_code"], logs[0]["prompt_tokens"], logs[0]["completion_tokens"]) == (200, 11, 7)


@pytest.mark.asyncio
async def test_completed_stream_without_provider_usage_is_estimated(monkeypatch, fake_redis):
    response, _, logs, background_tasks = await _start(monkeypatch, fake_redis, [_delta("some streamed words"), _delta(" more")])
    [_ async for _ in response.body_iterator]
    await background_tasks()

    assert logs[0]["prompt_tokens"] > 0 and logs[0]["completion_tokens"] > 0


@pytest.mark.asyncio
async def test_client_disconnect_still_records_usage(monkeypatch, fake_redis):
    response, _, logs, _ = await _start(monkeypatch, fake_redis, [_delta("first words"), _delta("never delivered"), USAGE_CHUNK])
    stream = response.body_iterator
    first = await stream.__anext__()
    assert json.loads(first.removeprefix("data: "))["choices"][0]["delta"]["content"] == "first words"

    await stream.aclose()  # what Starlette does when the client goes away
    await asyncio.sleep(0.05)  # let the detached log task run

    assert len(logs) == 1
    assert logs[0]["status_code"] == 499
    assert logs[0]["error_message"] == "client_disconnected"
    assert logs[0]["prompt_tokens"] > 0
