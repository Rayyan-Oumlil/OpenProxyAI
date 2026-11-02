"""Tool-calling messages must survive validation and reach LiteLLM exactly as sent."""
from app.schemas.chat import ChatCompletionRequest
from app.services.policy_service import policy_service

TOOL_CALL = {
    "id": "call_1",
    "type": "function",
    "function": {"name": "lookup", "arguments": '{"ssn": "123-45-6789"}'},
}

PAYLOAD = {
    "model": "openai/gpt-4o-mini",
    "messages": [
        {"role": "user", "content": "look it up"},
        {"role": "assistant", "content": None, "tool_calls": [TOOL_CALL]},
        {"role": "tool", "tool_call_id": "call_1", "name": "lookup", "content": "found"},
    ],
    "tools": [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}],
    "tool_choice": "auto",
    "parallel_tool_calls": False,
    "response_format": {"type": "json_schema", "json_schema": {"name": "r", "schema": {"type": "object"}}},
}


def test_assistant_tool_call_message_with_null_content_validates():
    request = ChatCompletionRequest.model_validate(PAYLOAD)
    assert request.messages[1].content is None


def test_assistant_message_without_content_key_validates():
    payload = {**PAYLOAD, "messages": [{"role": "assistant", "tool_calls": [TOOL_CALL]}]}
    assert ChatCompletionRequest.model_validate(payload).messages[0].content is None


def test_litellm_kwargs_keep_tool_fields():
    kwargs = ChatCompletionRequest.model_validate(PAYLOAD).model_dump(exclude_none=True)

    assert kwargs["messages"][1]["tool_calls"] == [TOOL_CALL]
    assert kwargs["messages"][2]["tool_call_id"] == "call_1"
    assert kwargs["messages"][2]["name"] == "lookup"
    for field in ("tools", "tool_choice", "parallel_tool_calls", "response_format"):
        assert kwargs[field] == PAYLOAD[field]


def test_policy_text_includes_tool_call_arguments_and_tolerates_null_content():
    request = ChatCompletionRequest.model_validate(PAYLOAD)
    text = policy_service._extract_chat_text(request)

    assert "123-45-6789" in text
    assert "look it up" in text


def test_policy_text_decodes_json_escaped_tool_call_arguments():
    """Escaped digits hide from regex scanners in the raw string but not from the model."""
    escaped = '{"ssn": "' + chr(92) + 'u0031' + chr(92) + 'u0032' + chr(92) + 'u0033-45-6789"}'
    assert "123" not in escaped
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "assistant", "tool_calls": [{"id": "c", "type": "function", "function": {"name": "f", "arguments": escaped}}]},
        ],
    }
    text = policy_service._extract_chat_text(ChatCompletionRequest.model_validate(payload))

    assert "123-45-6789" in text


def test_token_estimate_counts_passthrough_fields():
    from app.utils.token_estimator import estimate_tokens

    plain = ChatCompletionRequest.model_validate({"model": "m", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1})
    bloated = ChatCompletionRequest.model_validate(
        {
            "model": "m",
            "messages": [{"role": "assistant", "tool_calls": [{"function": {"arguments": "x" * 40_000}}]}],
            "max_tokens": 1,
        }
    )

    assert estimate_tokens(bloated) > estimate_tokens(plain) + 5_000


def test_tool_and_structured_requests_bypass_cache():
    from app.services.llm_service import _is_cache_unsafe

    assert _is_cache_unsafe(ChatCompletionRequest.model_validate(PAYLOAD))
    assert _is_cache_unsafe(ChatCompletionRequest.model_validate({"model": "m", "messages": [{"role": "user", "content": "x"}], "tools": [{"type": "function"}]}))
    assert _is_cache_unsafe(ChatCompletionRequest.model_validate({"model": "m", "messages": [{"role": "user", "content": "x"}], "response_format": {"type": "json_object"}}))
    assert not _is_cache_unsafe(ChatCompletionRequest.model_validate({"model": "m", "messages": [{"role": "user", "content": "x"}]}))
