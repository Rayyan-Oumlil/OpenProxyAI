"""Token estimation utilities for pre-flight rate-limiting decisions."""

from app.schemas.chat import ChatCompletionRequest


def estimate_tokens(request: ChatCompletionRequest) -> int:
	"""Conservative pre-flight token estimate for TPM checks."""
	content_chars = sum(len(str(message.content or "")) for message in request.messages)
	base_estimate = max(content_chars // 4, 1)
	buffer = request.max_tokens if request.max_tokens is not None else 500
	return max(base_estimate + max(buffer, 1), 1)
