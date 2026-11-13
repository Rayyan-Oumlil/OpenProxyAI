"""Inject X-OpenProxyAI-Request-Id header on every response.

Uses pure ASGI middleware (not BaseHTTPMiddleware) to avoid buffering
the response body — critical for SSE streaming in the LLM proxy.
"""

import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.utils.logging import request_id_ctx


class RequestIdMiddleware:
    """Generate a UUID-v4 per request, store in ContextVar, and inject as header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = uuid.uuid4().hex
        request_id_ctx.set(rid)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[Any] = list(message.get("headers", []))
                # A route that already stamped its own id (chat, modalities, conversations) wins: a second header would
                # reach clients as "id1, id2", which POST /v1/feedback cannot parse.
                if not any(name.lower() == b"x-openproxyai-request-id" for name, _ in headers):
                    headers.append((b"x-openproxyai-request-id", rid.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
