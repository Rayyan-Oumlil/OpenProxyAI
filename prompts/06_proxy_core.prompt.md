# Step 6 — Proxy Core (The Heart of OpenProxyAI)

> **Reference:** Follow `prompts/01_backend_backbone.prompt.md` for design decisions, especially the 8 "Critical Design Decisions" at the bottom. Steps 2–5 are complete — auth works and you can generate API keys.

---

## Context

Auth is working. Now build the actual proxy — `POST /v1/chat/completions` and `POST /v1/embeddings`. This endpoint is the entire product. An API key from Step 5 authenticates the request, and the response must be 100% OpenAI-compatible.

---

## What To Build This Session

### 1. `backend/app/schemas/chat.py`

OpenAI-compatible request/response schemas:

```python
class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list  # list for multimodal

class ChatCompletionRequest(BaseModel):
    model: str                              # e.g. "openai/gpt-4o", "anthropic/claude-3-5-sonnet"
    messages: list[Message]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: str | list[str] | None = None
    user: str | None = None                 # passthrough to provider
    # Any extra fields passed through to LiteLLM
    model_config = ConfigDict(extra="allow")

class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    encoding_format: str = "float"
```

Responses are NOT defined as Pydantic schemas — they're passed through raw from LiteLLM to preserve 100% OpenAI compatibility.

### 2. `backend/app/services/llm_service.py`

The core proxy service. Never call provider SDKs directly — always go through `litellm`.

```python
import litellm
from litellm import acompletion, completion_cost

class LLMService:

    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        org: Organization,
        user: User,
        api_key: APIKey,
        request_id: uuid.UUID,
    ) -> Response:
        """
        Non-streaming path:
        1. Select provider key (weighted random from llm_provider_keys table)
        2. Call litellm.acompletion()
        3. Calculate cost via litellm.completion_cost(completion_response=response)
        4. Schedule background task: log to request_logs, update Redis budget counter
        5. Return JSONResponse with upstream body + X-OpenProxyAI-* headers

        Streaming path (request.stream=True):
        1. Same provider selection
        2. Call litellm.acompletion(stream=True)
        3. Peek at first chunk — if it contains an error, return JSONResponse(502)
        4. Yield chunks to client via StreamingResponse (SSE format)
        5. Capture chunks inline to count tokens after stream ends
        6. After [DONE], calculate cost and schedule background log task
        7. Track ttft_ms from first chunk timestamp
        """

    async def embedding(
        self,
        request: EmbeddingRequest,
        org: Organization,
        user: User,
    ) -> Response: ...

    def _select_provider_key(self, org: Organization, provider: str) -> str:
        """Weighted random selection from org's active provider keys."""

    async def _build_litellm_kwargs(
        self,
        request: ChatCompletionRequest,
        api_key: str,
    ) -> dict:
        """
        Map request fields to litellm.acompletion kwargs.
        Set timeout=30. Set request_timeout=30.
        """
```

**Streaming implementation pattern (critical — from Helicone):**

```python
async def _stream_with_capture(
    self,
    litellm_stream,
    background_tasks: BackgroundTasks,
    log_kwargs: dict,
) -> AsyncGenerator[str, None]:
    chunks = []
    first_chunk_time: float | None = None

    async for chunk in litellm_stream:
        if first_chunk_time is None:
            first_chunk_time = time.perf_counter()

        chunks.append(chunk)
        # Yield the raw SSE line to the client immediately
        yield f"data: {chunk.model_dump_json()}\n\n"

    yield "data: [DONE]\n\n"

    # After stream completes, schedule the log — never before
    ttft_ms = int((first_chunk_time - start_time) * 1000) if first_chunk_time else None
    background_tasks.add_task(self._log_request, chunks=chunks, ttft_ms=ttft_ms, **log_kwargs)
```

### 3. `backend/app/services/audit_logger.py`

```python
async def log_request(
    db: AsyncSession,
    redis: Redis,
    request_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID | None,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: Decimal,
    latency_ms: int,
    ttft_ms: int | None,
    status_code: int,
    error_message: str | None = None,
) -> None:
    """
    1. INSERT into request_logs
    2. INCRBYFLOAT rl:usd:{org_id}:{today_iso} {cost_usd}   ← Redis budget counter
    3. EXPIRE that key to 48h (rolling TTL)
    This runs as a BackgroundTask — never blocks the response.
    """
```

### 4. `backend/app/routes/proxy.py`

```python
@router.post("/v1/chat/completions", tags=["Proxy"])
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    auth: ProxyAuth = Depends(),           # validates API key
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    request_id: uuid.UUID = Depends(get_request_id),
) -> Response:
    user, api_key = auth
    return await llm_service.chat_completion(
        request=request,
        org=user.organization,
        user=user,
        api_key=api_key,
        request_id=request_id,
        background_tasks=background_tasks,
    )

@router.post("/v1/embeddings", tags=["Proxy"])
async def embeddings(...) -> Response: ...
```

### 5. Response headers on every proxy response

Always inject these — whether streaming or not:

| Header | Value |
|---|---|
| `X-OpenProxyAI-Request-Id` | UUID for this request |
| `X-OpenProxyAI-Provider` | `openai` / `anthropic` / etc. |
| `X-OpenProxyAI-Model` | Actual model used (may differ from request if fallback) |
| `X-OpenProxyAI-Cost-USD` | Float, 6 decimal places |
| `X-OpenProxyAI-Latency-Ms` | Integer ms |
| `X-OpenProxyAI-TTFT-Ms` | Integer ms (streaming only, omit otherwise) |
| `X-OpenProxyAI-Gateway-Error` | `"false"` if provider failed, `"true"` if proxy failed |

### 6. Error handling

| Scenario | Status | Body |
|---|---|---|
| Provider 429 (rate limit) | 429 | `{"error": "provider_rate_limited", "detail": "...", "provider": "openai"}` |
| Provider 5xx | 502 | `{"error": "provider_error", "detail": "..."}` |
| Timeout (30s) | 504 | `{"error": "provider_timeout", "detail": "..."}` |
| Invalid model | 400 | `{"error": "invalid_model", "detail": "Model not supported"}` |
| No provider key configured | 503 | `{"error": "no_provider_key", "detail": "No active key for provider"}` |

In all error cases: log to `request_logs` with negative or ≥400 `status_code`.

---

## Done When

```bash
# Non-streaming call (real OpenAI API key required)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer opai_dev_XXXXX" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Say hello in 5 words"}]}'
# → valid OpenAI-format JSON response
# → headers include X-OpenProxyAI-Cost-USD, X-OpenProxyAI-Latency-Ms, etc.

# Streaming call
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer opai_dev_XXXXX" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Count to 5"}],"stream":true}'
# → SSE stream: data: {...}\n\n ... data: [DONE]\n\n
# → X-OpenProxyAI-TTFT-Ms present in response headers

# Verify request was logged
docker compose exec postgres psql -U openproxyai \
  -c "SELECT model, provider, prompt_tokens, cost_usd, status_code FROM request_logs LIMIT 5;"
# → row with real token counts and cost

# Embeddings
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Authorization: Bearer opai_dev_XXXXX" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/text-embedding-ada-002","input":"hello world"}'
# → {"object":"list","data":[{"object":"embedding","embedding":[...],"index":0}],...}
```
