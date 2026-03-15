"""Tests for optional Langfuse tracing service."""

import pytest
from unittest.mock import MagicMock, patch


def _reset_module():
    """Reset module-level singleton state between tests."""
    import app.services.langfuse_service as mod

    mod._client = None
    mod._initialized = False


def test_is_enabled_returns_false_when_not_configured():
    _reset_module()
    with patch("app.config.settings") as mock_settings:
        mock_settings.LANGFUSE_SECRET_KEY = ""
        mock_settings.LANGFUSE_PUBLIC_KEY = ""
        mock_settings.LANGFUSE_HOST = "https://cloud.langfuse.com"
        from app.services import langfuse_service

        _reset_module()
        assert not langfuse_service.is_enabled()


@pytest.mark.asyncio
async def test_send_trace_noop_when_not_configured():
    _reset_module()
    # Should not raise
    from app.services import langfuse_service

    _reset_module()
    await langfuse_service.send_trace(
        request_id="test-id",
        org_id="org-1",
        user_id="user-1",
        model="openai/gpt-4o",
        provider="openai",
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.001,
        latency_ms=500,
        ttft_ms=100,
        status_code=200,
        policy_action=None,
        error_message=None,
    )


@pytest.mark.asyncio
async def test_send_trace_calls_langfuse_when_configured():
    _reset_module()
    mock_trace = MagicMock()
    mock_client = MagicMock()
    mock_client.trace.return_value = mock_trace
    mock_client.flush = MagicMock()

    from app.services import langfuse_service

    _reset_module()

    with patch.object(langfuse_service, "_get_client", return_value=mock_client):
        await langfuse_service.send_trace(
            request_id="req-abc",
            org_id="org-1",
            user_id="user-1",
            model="openai/gpt-4o",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.001,
            latency_ms=500,
            ttft_ms=100,
            status_code=200,
            policy_action="allow",
            error_message=None,
        )

    mock_client.trace.assert_called_once()
    call_kwargs = mock_client.trace.call_args.kwargs
    assert call_kwargs["id"] == "req-abc"
    assert call_kwargs["user_id"] == "user-1"
    mock_trace.generation.assert_called_once()
    mock_client.flush.assert_called_once()


@pytest.mark.asyncio
async def test_send_trace_swallows_exceptions():
    _reset_module()
    mock_client = MagicMock()
    mock_client.trace.side_effect = RuntimeError("Langfuse down")

    from app.services import langfuse_service

    _reset_module()

    with patch.object(langfuse_service, "_get_client", return_value=mock_client):
        # Should not raise
        await langfuse_service.send_trace(
            request_id="req-xyz",
            org_id="org-1",
            user_id="user-1",
            model="openai/gpt-4o",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.001,
            latency_ms=500,
            ttft_ms=None,
            status_code=200,
            policy_action=None,
            error_message=None,
        )
