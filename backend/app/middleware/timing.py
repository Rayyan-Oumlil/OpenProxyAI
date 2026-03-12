"""Measure and inject X-OpenProxyAI-Latency-Ms header on every response.

Uses pure ASGI middleware (not BaseHTTPMiddleware) to avoid buffering
the response body — critical for SSE streaming in the LLM proxy.
"""

import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class TimingMiddleware:
    """Record wall-clock time and expose as X-OpenProxyAI-Latency-Ms."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                headers: list[Any] = list(message.get("headers", []))
                headers.append((b"x-openproxyai-latency-ms", str(elapsed_ms).encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
