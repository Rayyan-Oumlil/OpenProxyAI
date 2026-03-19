# Architecture Decision Records

These findings come from reading the actual source code of LiteLLM (`proxy_server.py`, `route_llm_request.py`), Portkey Gateway (`src/index.ts`, `middlewares/hooks/`), Helicone (`worker/src/lib/HeliconeProxyRequest/`), Bifrost, and Envoy AI Gateway. They explain why OpenProxyAI is built the way it is.

---

## ADR-1: Keep the proxy handler thin

**What LiteLLM got wrong:** `proxy_server.py` is 508KB — a single-file monolith that grew organically. It handles auth, routing, caching, compliance, UI endpoints, RAG, vector stores, and evals in one file. Impossible to audit and extend safely.

**What Portkey got right:** Their `chatCompletionsHandler.ts` is 57 lines. It parses the request, reads config, calls the routing engine, and returns the response. Everything else (logging, validation, caching) is middleware registered separately.

**Decision:** The proxy handler must never exceed ~50 lines. All complexity lives in services and hooks.

```python
@router.post("/v1/chat/completions")
async def chat_completions(request: Request, key=Depends(validate_api_key)):
    body = await request.json()
    body = await run_before_hooks(body, key)
    response = await llm_service.complete(body)
    background_tasks.add_task(log_request, ...)
    return response
```

---

## ADR-2: Async logging — never block the response path

**Source:** Helicone's `ProxyRequestHandler.ts` and `ReadableInterceptor`.

The key challenge: for streaming responses, you don't know the full response body until the stream ends — but you must return the first token immediately.

Helicone wraps the response stream with an interceptor that passes chunks to the client AND buffers them internally. After the stream completes, `interceptor.waitForStream()` returns the full body for logging.

**Decision for OpenProxyAI:** Use `asyncio.create_task()` to schedule logging as a background task after the response is returned. The audit log is always written, but never on the critical path.

Key metrics always logged: `ttft_ms`, `total_latency_ms`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `status_code`.

Status code conventions: positive values = HTTP codes from the provider. Negative values = proxy-internal errors (`-2` = timeout, `-3` = cancelled, `-4` = blocked by policy).

---

## ADR-3: Hook system for guardrails

**Source:** Portkey's `middlewares/hooks/` with `beforeRequestHooks` and `afterRequestHooks`.

Each hook receives the full request context and can pass, modify, or block. Hooks are registered separately from the handler — never inline.

**Decision:** `before_request` hooks (policy evaluation, PII detection, prompt injection) run before the LLM call. `after_request` hooks (response guardrails, response PII redaction) run after the response is received. The handler calls `run_before_hooks()` and `run_after_hooks()` — it has no knowledge of individual policies.

---

## ADR-4: Use LiteLLM as a library, not a server

**Source:** LiteLLM's `route_llm_request.py`.

LiteLLM's Router handles provider routing, model aliases, retries, and fallbacks. The key call is always `await llm_router.acompletion(**data)`.

**Decision:** Use `litellm.acompletion()` and `Router` as a library call inside `LLMService`. Do not run LiteLLM's proxy server — that would duplicate the entire gateway layer. OpenProxyAI wraps LiteLLM the same way a web framework wraps a database driver.

Provider keys are loaded from the database at request time, not from a static config file. This enables live key rotation and per-org provider configuration.

---

## ADR-5: ClickHouse for analytics at scale

**Source:** Helicone's `clickhouse/` folder and `ClickhouseClientWrapper`.

**Why PostgreSQL is insufficient at scale:**

| Query | PostgreSQL (10M rows) | ClickHouse (10M rows) |
|---|---|---|
| Total cost by org last 30d | ~8 seconds | ~50ms |
| Requests by model last 7d | ~5 seconds | ~30ms |
| P95 latency by provider | ~12 seconds | ~80ms |

PostgreSQL is OLTP (fast writes, fast lookups by PK). ClickHouse is OLAP (fast analytical aggregates over millions of rows).

**Decision:** Phase 1-2 log to PostgreSQL. Phase 3+ dual-write to ClickHouse via a fire-and-forget sidecar. ClickHouse is opt-in via `CLICKHOUSE_URL` env var. If it's not configured, the gateway works normally — ClickHouse is a sidecar, not a core dependency.

---

## ADR-6: What not to build until later

After studying all reference implementations, these features look important but add complexity with minimal value early:

| Feature | Source | Decision |
|---|---|---|
| ~~Semantic caching~~ | LiteLLM | **Shipped** — 3-tier cache (L1 in-memory + L2 Redis + L3 pgvector) |
| ~~Multi-region~~ | Helicone | **Shipped (Tier 1)** — config-based region routing. Tier 2 (self-hosted) deferred |
| WASM plugin system | Envoy | Enterprise Phase 4 |
| WebSocket/Realtime proxy | Portkey | Almost no enterprise use case yet |
| Auto-updated model cost DB | LiteLLM | Use `litellm.completion_cost()` instead |

---

## ADR-7: Always distinguish gateway errors from provider errors

**Source:** Bifrost's `IsBifrostError` boolean on every error response.

**Why this matters:**
1. **Fallback logic**: If the gateway itself failed (DB down, config error), do NOT fall back to another provider — the retry will also fail. Only fall back on provider errors (429, 500-504 from the upstream).
2. **Alerting**: A spike in gateway errors is a bug in OpenProxyAI code. A spike in provider errors is an upstream outage. These need different alert channels and different SLA handling.

**Decision:** Every error response includes `X-OpenProxyAI-Gateway-Error: true/false`.
- `true` = failure inside the proxy (auth, DB, hook, config)
- `false` = failure at the upstream provider (OpenAI 429, Anthropic timeout)

---

## ADR-8: Peek at first SSE chunk before returning StreamingResponse

**Source:** LiteLLM's `create_response()` in `common_request_processing.py`.

Without this, the client receives `HTTP 200 OK` with `Content-Type: text/event-stream` — then gets an error buried in the stream body. Most client SDKs handle this incorrectly (showing `undefined` or crashing).

**Decision:** After starting the stream, peek at the first chunk. If it contains an error object, return a `JSONResponse` with the correct status code instead of a `StreamingResponse`. This guarantees clients always get a proper HTTP error — never a 200 that hides a failure.

---

## ADR-9: Selective fallback — only on transient provider errors

**Source:** Portkey's `tryTargetsRecursively()` with `onStatusCodes` filter.

Falling back on every non-2xx response creates silent bugs:
- `400 Bad Request` from OpenAI means the request is malformed. Falling back to Anthropic will also return 400 — double latency, double cost, no benefit.
- `401 Unauthorized` means the API key is wrong. No fallback helps.
- `413 Payload Too Large` means the prompt is too long. No fallback helps.

**Decision:** Only fall back on transient infrastructure errors: `429`, `500`, `502`, `503`, `504`. Never fall back on `4xx` client errors.

---

## ADR-10: Materialized views for dashboard performance

**Source:** Helicone's ClickHouse materialized views.

Analytics queries (`SELECT SUM(cost_usd) GROUP BY model`) over millions of rows are expensive if run on raw tables. Materialized views pre-aggregate the data so dashboard queries return in milliseconds.

**Decision:** `mv_daily_spend` pre-aggregates cost and token usage by org, model, and day. It refreshes via APScheduler every 5 minutes. The analytics overview endpoint reads from the view, not the raw `request_logs` table. This keeps the dashboard fast even at millions of requests.

---

## ADR-11: 3-tier semantic cache with pgvector

**Source:** LiteLLM's `DualCache` pattern (in-memory + Redis), extended with vector similarity.

**Why three tiers:**
- L1 (in-memory TTLCache) — sub-millisecond for hot paths, no network hop
- L2 (Redis) — exact-match across all instances, survives restarts
- L3 (pgvector) — catches semantically equivalent but not identical prompts (e.g., "What is 2+2?" vs "What's two plus two?")

**Key decision:** L3 fire-and-forget writes must create their own DB session. The request-scoped SQLAlchemy session is closed by FastAPI's dependency lifecycle after the response is sent — any `asyncio.create_task()` using that session will crash with "Session is closed." This is a critical pattern: **fire-and-forget tasks are sidecars and must manage their own connections.**

**Threshold:** Default 0.95 cosine similarity. Lower thresholds risk returning wrong answers; higher thresholds reduce hit rate. Configurable via `SEMANTIC_CACHE_SIMILARITY_THRESHOLD`.

---

## ADR-12: Data residency via region-tagged provider keys

**Source:** 65% of enterprise RFPs require geographic data isolation.

**Decision:** Config-based Tier 1 approach:
- `data_region` field on `organizations` (`us`, `eu`, `ap`)
- `region` field on `llm_provider_keys` (`us`, `eu`, `ap`, `global`)
- SQL filter: `WHERE region = data_region OR region = 'global'`

This ensures EU orgs never route through US-only keys. The `global` value allows shared keys (e.g., Azure's EU-hosted endpoint accessible to all regions).

**Not built (Tier 2):** Self-hosted air-gapped deployment, license key validation. Deferred until first enterprise customer requires on-premise.

---

## ADR-13: Compliance templates as frozen dataclasses

**Source:** 35% of enterprise RFPs ask for industry-specific pre-built policies.

**Decision:** Templates are frozen Python dataclasses (`@dataclass(frozen=True)`) — not database rows. This means:
- Templates are versioned with the code, not with customer data
- No migration needed to add/update templates
- Templates can't be mutated at runtime

**Apply semantics:** Merge, not replace. When applying a template, existing `allowed_models` and `model_rate_limits` are preserved. The template adds its PII rules, keywords, and enforcement mode on top. This prevents a template apply from accidentally removing a customer's custom model allowlist.

Redis cache is invalidated immediately after applying a template. An audit log entry records the template application.
