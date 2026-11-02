"""Token estimation utilities for pre-flight rate-limiting decisions."""

import json

from app.schemas.chat import ChatCompletionRequest


def _extras_chars(extras: dict | None) -> int:
	"""Size of pass-through fields (tool_calls, tools, response_format, ...) that are forwarded upstream."""
	if not extras:
		return 0
	return len(json.dumps(extras, default=str))


def estimate_tokens(request: ChatCompletionRequest) -> int:
	"""Conservative pre-flight token estimate for TPM checks."""
	content_chars = sum(len(str(message.content or "")) for message in request.messages)
	content_chars += sum(_extras_chars(message.model_extra) for message in request.messages)
	content_chars += _extras_chars(request.model_extra)
	base_estimate = max(content_chars // 4, 1)
	buffer = request.max_tokens if request.max_tokens is not None else 500
	return max(base_estimate + max(buffer, 1), 1)
