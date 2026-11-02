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
