# Step 7 — Rate Limiting & Cost Tracking

> **Reference:** Follow `prompts/01_backend_backbone.prompt.md`. Steps 2–6 complete — the proxy works end to end.

---

## Context

The proxy routes LLM calls and logs them. Now enforce the limits: rate limits per org, token budget per minute, and daily spend caps. These must fire *before* the request reaches the LLM provider — never after.

---

## What To Build This Session

### 1. `backend/app/services/rate_limiter.py`

Three independent Redis counters checked on every proxy request. All three must pass or the request is blocked.

```python
class RateLimiter:

    async def check_and_consume(
        self,
        redis: Redis,
        org: Organization,
        user: User,
        estimated_tokens: int = 1000,    # conservative pre-flight estimate
    ) -> None:
        """
        Runs three checks in order. Raises HTTP 429 on the first failure.
        Each 429 response body includes 'limit_type' indicating which limit fired.

        After all checks pass, atomically increment all three counters.
        Use a Redis pipeline (MULTI/EXEC) for the increments — never do them separately.
        """

    async def _check_requests_per_minute(
        self, redis: Redis, org_id: uuid.UUID, limit: int
    ) -> int:
        """
        Sliding window using ZSET:
          ZADD rl:req:{org_id} {now_ms} {request_uuid}
          ZREMRANGEBYSCORE rl:req:{org_id} 0 {now_ms - 60000}
          ZCARD rl:req:{org_id}
          EXPIRE rl:req:{org_id} 120
        Returns current count. Caller raises 429 if count >= limit.
        """

    async def _check_tokens_per_minute(
        self, redis: Redis, org_id: uuid.UUID, limit: int, estimated_tokens: int
    ) -> int:
        """
        Fixed window (current minute bucket):
          key = rl:tpm:{org_id}:{minute_bucket}   (minute_bucket = epoch // 60)
          INCRBY key estimated_tokens
          EXPIRE key 120
        Returns new total. Caller raises 429 if total > limit.
        """

    async def _check_daily_budget(
        self, redis: Redis, org_id: uuid.UUID, limit_usd: float
    ) -> float:
        """
        Read from Redis (set by audit_logger after each request):
          GET rl:usd:{org_id}:{today_iso}
        Returns current spend as float. Caller raises 429 if spend >= limit.
        """
```

**429 response format:**
```json
{
  "error": "rate_limit_exceeded",
  "limit_type": "requests_per_minute",   // or "tokens_per_minute" or "budget_daily_usd"
  "detail": "60 requests/minute limit reached. Resets in 45 seconds.",
  "retry_after": 45
}
```

**Rate limit headers (on every proxy response, not just 429s):**
```
X-RateLimit-Requests-Limit: 60
X-RateLimit-Requests-Remaining: 42
X-RateLimit-Tokens-Limit: 100000
X-RateLimit-Tokens-Remaining: 87500
X-RateLimit-Budget-Daily-USD: 50.00
X-RateLimit-Budget-Remaining-USD: 38.42
X-RateLimit-Reset: 1741824060    (Unix timestamp when minute window resets)
```

### 2. Wire rate limiter into the proxy route

In `backend/app/routes/proxy.py`, call `rate_limiter.check_and_consume()` before calling `llm_service.chat_completion()`. The check must happen synchronously in the request path — not as a background task.

```python
@router.post("/v1/chat/completions")
async def chat_completions(...):
    user, api_key = auth

    # This must happen before any LLM call
    await rate_limiter.check_and_consume(
        redis=redis,
        org=user.organization,
        user=user,
        estimated_tokens=estimate_tokens(request),   # rough pre-call estimate
    )

    return await llm_service.chat_completion(...)
```

### 3. `backend/app/services/cost_tracker.py`

Post-request cost accounting (already partially in `audit_logger.py` — extend it):

```python
async def check_user_budget(
    redis: Redis,
    user: User,
) -> None:
    """
    Check user-level daily budget in addition to org-level.
    User budget is separate from org budget — both must pass.
    Read from Redis key: rl:usd:user:{user_id}:{today_iso}
    Raise 429 with limit_type="user_budget_daily_usd" if exceeded.
    """

async def get_org_spend_today(redis: Redis, org_id: uuid.UUID) -> float:
    """Read current day spend from Redis. Used for rate limit headers."""

async def get_user_spend_today(redis: Redis, user_id: uuid.UUID) -> float:
    """Read current day spend for a specific user."""

async def alert_at_threshold(
    redis: Redis,
    org: Organization,
    current_spend: float,
    threshold: float = 0.8,
) -> None:
    """
    If current_spend >= budget * threshold AND we haven't alerted yet today:
      SET alert:budget:{org_id}:{today} 1 EX 86400
      Log a WARNING (email/webhook notification is Phase 2)
    """
```

### 4. `estimate_tokens()` utility

Simple pre-flight token estimate to use for the `tokens_per_minute` check *before* the LLM call:

```python
def estimate_tokens(request: ChatCompletionRequest) -> int:
    """
    Rough estimate: sum of character counts of all messages / 4.
    Add max_tokens if specified, else add 500 as buffer.
    This is a conservative overestimate — real count comes from LiteLLM after the call.
    """
```

---

## Done When

```bash
# Set a very low rate limit for testing (temporarily edit .env or org record in DB)
# e.g. DEFAULT_RATE_LIMIT_RPM=2

# First two calls succeed
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer opai_dev_XXXXX" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'
# → 200, headers show X-RateLimit-Requests-Remaining: 1

# Third call within the same minute
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer opai_dev_XXXXX" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'
# → 429 {"error":"rate_limit_exceeded","limit_type":"requests_per_minute",...}

# Verify budget counter exists in Redis after successful calls
docker compose exec redis redis-cli KEYS "rl:usd:*"
# → rl:usd:{org-uuid}:{today}

docker compose exec redis redis-cli GET "rl:usd:{org-uuid}:{today}"
# → "0.000123"   ← actual spend accumulated

# Rate limit headers present on 200 responses
curl -I -X POST http://localhost:8000/v1/chat/completions ...
# → X-RateLimit-Requests-Remaining: N
# → X-RateLimit-Budget-Remaining-USD: N
```
