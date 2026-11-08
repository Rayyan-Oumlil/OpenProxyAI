"""Audit writes for blocked requests are scheduled, never awaited inline (P0-7)."""
import asyncio
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

from app.services import llm_service as llm_module
from app.services.policy_service import PolicyDecision
from tests.conftest import FakeDB


@pytest.mark.asyncio
async def test_policy_block_returns_before_log_write(monkeypatch, fake_redis):
    started = asyncio.Event()
    finished = asyncio.Event()

    async def slow_log(**kwargs):
        started.set()
        await asyncio.sleep(0.05)
        finished.set()

    async def block(req, cfg):
        return PolicyDecision(allowed=False, action="block", reason_code="test", detail="blocked")

    monkeypatch.setattr(llm_module, "log_request", slow_log)
    monkeypatch.setattr(llm_module.policy_service, "evaluate_chat_request", block)

    user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("50"))
    background_tasks = BackgroundTasks()
    response = await llm_module.llm_service.chat_completion(
        request=llm_module.ChatCompletionRequest(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]),
        db=FakeDB(),
        redis=fake_redis,
        user=user,
        api_key=SimpleNamespace(id=uuid4()),
        request_id=uuid4(),
        background_tasks=background_tasks,
        http_request=None,
    )

    assert response.status_code == 446
    assert not started.is_set(), "log_request ran inline before the response was returned"
    assert len(background_tasks.tasks) == 1

    await background_tasks()
    assert finished.is_set()


@pytest.mark.asyncio
async def test_detached_log_runs_without_blocking_caller(monkeypatch):
    done = asyncio.Event()

    async def slow_log(**kwargs):
        await asyncio.sleep(0.02)
        done.set()

    monkeypatch.setattr(llm_module, "log_request", slow_log)
    llm_module._log_detached(model="m")

    assert not done.is_set()
    await asyncio.wait_for(done.wait(), timeout=1)
