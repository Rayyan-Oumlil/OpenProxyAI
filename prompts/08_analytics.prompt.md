# Step 8 — Analytics API

> **Reference:** Follow `prompts/01_backend_backbone.prompt.md`. Steps 2–7 complete — rate limiting works.

---

## Context

`request_logs` now has real data accumulating. Build the analytics API that powers the dashboard. All queries must hit the `mv_daily_spend` materialized view — never raw `request_logs` for aggregate queries. Raw `request_logs` is for single-record lookups only (e.g. fetching one specific log entry).

---

## What To Build This Session

### 1. Materialized view refresh job

Add to `backend/app/main.py` lifespan — schedule a background refresh every 5 minutes using `apscheduler`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def refresh_materialized_view(db_session_factory):
    async with db_session_factory() as session:
        await session.execute(
            text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_spend")
        )
        await session.commit()
        logger.info("mv_daily_spend refreshed")

# In lifespan:
scheduler = AsyncIOScheduler()
scheduler.add_job(
    refresh_materialized_view,
    "interval",
    minutes=5,
    args=[AsyncSessionLocal],
    id="refresh_mv_daily_spend",
)
scheduler.start()
```

The `CONCURRENTLY` keyword means postgres does a non-blocking refresh — old data stays visible during the refresh. This works because the materialized view was created with `CREATE UNIQUE INDEX` on its key column.

### 2. `backend/app/schemas/analytics.py`

```python
class UsageOverview(BaseModel):
    period_days: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    avg_ttft_ms: float

class CostByModel(BaseModel):
    model: str
    provider: str
    requests: int
    tokens: int
    cost_usd: float

class CostByUser(BaseModel):
    user_id: uuid.UUID
    email: str
    requests: int
    tokens: int
    cost_usd: float

class DailyUsageTrend(BaseModel):
    date: str            # ISO date "2024-01-15"
    requests: int
    tokens: int
    cost_usd: float
    avg_latency_ms: float

class AnalyticsResponse(BaseModel):
    overview: UsageOverview
    by_model: list[CostByModel]
    by_user: list[CostByUser]
    daily_trend: list[DailyUsageTrend]
    generated_at: datetime
```

### 3. `backend/app/services/analytics_service.py`

```python
class AnalyticsService:

    async def get_overview(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        period_days: int = 30,
    ) -> AnalyticsResponse:
        """
        Orchestrates all 4 sub-queries and assembles AnalyticsResponse.
        Pass org_id to every query — users only ever see their own org's data.
        """

    async def _overview_stats(
        self, db: AsyncSession, org_id: uuid.UUID, since: date
    ) -> UsageOverview:
        """
        Hit mv_daily_spend for aggregates.
        For failed_requests and avg_ttft_ms, hit request_logs
        (mv_daily_spend doesn't store per-request error status).
        """

    async def _cost_by_model(
        self, db: AsyncSession, org_id: uuid.UUID, since: date
    ) -> list[CostByModel]:
        """
        SELECT model, provider, SUM(total_requests), SUM(total_tokens), SUM(total_cost_usd)
        FROM mv_daily_spend
        WHERE org_id = :org_id AND date >= :since
        GROUP BY model, provider
        ORDER BY total_cost_usd DESC
        LIMIT 20
        """

    async def _cost_by_user(
        self, db: AsyncSession, org_id: uuid.UUID, since: date
    ) -> list[CostByUser]:
        """
        JOIN mv_daily_spend with users table to get email.
        GROUP BY user_id.
        LIMIT 50.
        """

    async def _daily_trend(
        self, db: AsyncSession, org_id: uuid.UUID, since: date
    ) -> list[DailyUsageTrend]:
        """
        SELECT date, SUM(total_requests), SUM(total_tokens), SUM(total_cost_usd),
               AVG(avg_latency_ms)
        FROM mv_daily_spend
        WHERE org_id = :org_id AND date >= :since
        GROUP BY date
        ORDER BY date ASC
        """
```

### 4. `backend/app/routes/analytics.py`

```python
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

@router.get("/overview", response_model=AnalyticsResponse)
async def get_analytics_overview(
    period_days: int = Query(default=30, ge=1, le=90),
    auth: ProxyAuth = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns aggregated analytics for the authenticated user's organization.
    Users can only see data for their own org_id — enforced here,
    not just in the query.
    """
    return await analytics_service.get_overview(
        db=db,
        org_id=auth.user.org_id,
        period_days=period_days,
    )

@router.get("/logs", response_model=Page[RequestLogItem])
async def get_request_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, le=200),
    model: str | None = Query(default=None),
    status: str | None = Query(default=None),  # "success" | "error"
    auth: ProxyAuth = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Paginated raw log listing. Hits request_logs directly (single-record retrieval).
    Always filters by org_id. Supports optional model and status filters.
    """
```

### 5. `backend/app/schemas/logs.py`

```python
class RequestLogItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    model: str
    provider: str
    status: str            # "success" | "error"
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    ttft_ms: int | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
```

---

## Done When

```bash
# Trigger a few test requests so mv_daily_spend has data
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer opai_dev_XXXXX" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'

# Manually refresh the view (don't wait 5 minutes during development)
docker compose exec postgres psql -U openproxyai -d openproxyai \
  -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_spend;"

# Check overview endpoint returns real data
curl http://localhost:8000/api/v1/analytics/overview \
  -H "Authorization: Bearer opai_dev_XXXXX"
# → 200 JSON with non-zero total_requests, total_cost_usd > 0

# Check daily trend has entries
# → daily_trend array has at least one entry for today's date

# Check logs endpoint  
curl "http://localhost:8000/api/v1/analytics/logs?page=1&page_size=10" \
  -H "Authorization: Bearer opai_dev_XXXXX"
# → 200 JSON with items array containing real log entries

# Verify org isolation — a second org's token cannot see first org's data
# Register second user, create API key, fetch analytics
# → total_requests: 0 (sees empty data, not another org's data)

# Verify scheduler is running
# Check logs for "mv_daily_spend refreshed" message within 5 minutes of startup
docker compose logs api | grep "mv_daily_spend refreshed"
```
