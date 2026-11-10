"""Fake OpenAI-compatible upstream for end-to-end pipeline tests.

Serves /v1/chat/completions (JSON + SSE), /v1/embeddings and /v1/models. Behaviour is chosen by
the model name sent upstream (LiteLLM strips the ``openai/`` prefix) or by the bearer key:

    fail-429 / fail-500   -> that HTTP status
    slow                  -> responds after 1 s
    bad-json              -> 200 with a body that is not JSON
    pii-response          -> completion text containing an SSN
    [judge-score=N] in the last user message -> a judge's JSON reply {"score": N, "reason": ...}
    mid-stream-error      -> SSE that is cut after the first content chunk
    key "sk-bad"          -> 429 for any model (to exercise key fallback)

Every request is recorded; read them with GET /__calls and clear with POST /__reset.
"""

import asyncio
import hashlib
import json
import re
import socket
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

PROMPT_TOKENS = 10
COMPLETION_TOKENS = 5
PII_TEXT = "Your SSN is 123-45-6789."


JUDGE_MARKER = re.compile(r"\[judge-score=(\d+)\]")


def _completion_text(body: dict[str, Any]) -> str:
    if body.get("model") == "pii-response":
        return PII_TEXT
    last = next((m for m in reversed(body.get("messages", [])) if m.get("role") == "user"), {})
    judged = JUDGE_MARKER.search(str(last.get("content")))
    if judged:
        return json.dumps({"score": int(judged.group(1)), "reason": "fake judge"})
    return f"echo: {last.get('content')}"


BIG_USAGE_MARKER = "[big-usage]"
# Priced as gpt-4o-mini this is about $0.02: over a $0.01 daily budget, yet under the 100k tokens/minute limit
# (a bigger number would trip the rate limit, 429, before the budget check, 402).
BIG_PROMPT_TOKENS = 50_000
BIG_COMPLETION_TOKENS = 20_000


def _usage(big: bool = False) -> dict[str, int]:
    """Normal responses report a handful of tokens; a prompt containing [big-usage] reports tens of thousands,
    which costs real money under the model's price and lets a demo hit a budget with one request."""
    prompt, completion = (BIG_PROMPT_TOKENS, BIG_COMPLETION_TOKENS) if big else (PROMPT_TOKENS, COMPLETION_TOKENS)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}


def _wants_big_usage(body: dict[str, Any]) -> bool:
    last = next((m for m in reversed(body.get("messages", [])) if m.get("role") == "user"), {})
    return BIG_USAGE_MARKER in str(last.get("content"))


def _chunk(model: str, delta: dict[str, Any], finish: str | None = None) -> str:
    payload = {
        "id": "chatcmpl-fake",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload)}\n\n"


def create_app() -> FastAPI:
    app = FastAPI()
    calls: list[dict[str, Any]] = []

    @app.get("/__calls")
    async def get_calls() -> list[dict[str, Any]]:
        return calls

    @app.post("/__reset")
    async def reset() -> dict[str, bool]:
        calls.clear()
        return {"ok": True}

    @app.get("/v1/models")
    async def models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": "gpt-4o-mini", "object": "model"}]}

    @app.post("/v1/embeddings")
    async def embeddings(request: Request) -> dict[str, Any]:
        body = await request.json()
        calls.append({"path": "/v1/embeddings", "authorization": request.headers.get("authorization"), "body": body})
        inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
        data = [
            {
                "object": "embedding",
                "index": i,
                "embedding": [b / 255 for b in hashlib.sha256(str(text).encode()).digest()[:8]],
            }
            for i, text in enumerate(inputs)
        ]
        return {
            "object": "list",
            "data": data,
            "model": body["model"],
            "usage": {"prompt_tokens": PROMPT_TOKENS, "total_tokens": PROMPT_TOKENS},
        }

    @app.post("/v1/chat/completions")
    async def chat(request: Request) -> Response:
        body = await request.json()
        authorization = request.headers.get("authorization")
        calls.append({"path": "/v1/chat/completions", "authorization": authorization, "body": body})
        model = body.get("model", "")

        if authorization == "Bearer sk-bad" or model == "fail-429":
            return JSONResponse({"error": {"message": "rate limited", "type": "rate_limit_error"}}, status_code=429)
        if model == "fail-500":
            return JSONResponse({"error": {"message": "boom", "type": "server_error"}}, status_code=500)
        if model == "slow":
            await asyncio.sleep(1)
        if model == "bad-json":
            return Response("<<not json>>", media_type="application/json")

        text = _completion_text(body)
        big = _wants_big_usage(body)
        if body.get("stream"):
            include_usage = (body.get("stream_options") or {}).get("include_usage")
            return StreamingResponse(
                _sse(model, text, include_usage=bool(include_usage), fail_midway=model == "mid-stream-error", big=big),
                media_type="text/event-stream",
            )

        return JSONResponse(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "created": 0,
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": _usage(big),
            }
        )

    return app


async def _sse(model: str, text: str, *, include_usage: bool, fail_midway: bool, big: bool = False) -> AsyncIterator[str]:
    yield _chunk(model, {"role": "assistant", "content": ""})
    for index, word in enumerate(text.split(" ")):
        yield _chunk(model, {"content": word if index == 0 else f" {word}"})
        if fail_midway:
            raise RuntimeError("fake upstream: connection cut mid-stream")
    yield _chunk(model, {}, finish="stop")
    if include_usage:
        usage_chunk = {"id": "chatcmpl-fake", "object": "chat.completion.chunk", "created": 0, "model": model, "choices": [], "usage": _usage(big)}
        yield f"data: {json.dumps(usage_chunk)}\n\n"
    yield "data: [DONE]\n\n"


class FakeUpstream:
    """Runs the fake app on a random local port in a background thread."""

    def __init__(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self._server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=self.port, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> None:
        self._thread.start()
        deadline = time.time() + 10
        while not self._server.started:
            if time.time() > deadline:
                raise RuntimeError("fake upstream did not start")
            time.sleep(0.05)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
