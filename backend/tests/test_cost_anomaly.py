"""Tests for cost anomaly detection."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_no_alert_below_threshold():
    """No webhook fires when spend is within normal range."""
    from app.services.cost_tracker import CostTrackerService

    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda k: b"1.00" if "rl:usd" in k else None)
    redis.zadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    # Return 5 baseline entries all at $1/day
    redis.zrangebyscore = AsyncMock(return_value=[
        b"2026-03-09:1.0", b"2026-03-10:1.0", b"2026-03-11:1.0",
        b"2026-03-12:1.0", b"2026-03-13:1.0",
    ])

    db = AsyncMock()
    org = MagicMock()
    org.settings = {}

    tracker = CostTrackerService()
    with patch("app.services.webhook_service.dispatch_event", new_callable=AsyncMock) as mock_dispatch:
        await tracker.check_anomaly(redis, "org-123", None, db, org)
    mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_alert_fires_when_above_threshold():
    """Webhook fires when today's spend > 3x baseline average."""
    from app.services.cost_tracker import CostTrackerService
    from app.config import settings

    redis = AsyncMock()
    # Today's spend is 30x baseline (1.0 avg), well above 3x multiplier
    redis.get = AsyncMock(side_effect=lambda k: b"30.00" if "rl:usd" in k else None)
    redis.zadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.zrangebyscore = AsyncMock(return_value=[
        b"2026-03-09:1.0", b"2026-03-10:1.0", b"2026-03-11:1.0",
    ])
    redis.setex = AsyncMock(return_value=True)

    db = AsyncMock()
    org = MagicMock()
    org.settings = {}

    tracker = CostTrackerService()
    with patch("app.services.webhook_service.dispatch_event", new_callable=AsyncMock) as mock_dispatch:
        await tracker.check_anomaly(redis, "org-123", None, db, org)
    mock_dispatch.assert_called_once()
    call_kwargs = mock_dispatch.call_args.kwargs
    assert call_kwargs["event_type"] == "cost.anomaly"
    assert call_kwargs["data"]["today_spend_usd"] == 30.0


@pytest.mark.asyncio
async def test_alert_rate_limited_no_double_fire():
    """Alert does not fire a second time within the same hour."""
    from app.services.cost_tracker import CostTrackerService

    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda k: b"1" if "anomaly_fired" in k else b"30.00")
    redis.zadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.zrangebyscore = AsyncMock(return_value=[
        b"2026-03-09:1.0", b"2026-03-10:1.0", b"2026-03-11:1.0",
    ])

    db = AsyncMock()
    org = MagicMock()
    org.settings = {}

    tracker = CostTrackerService()
    with patch("app.services.webhook_service.dispatch_event", new_callable=AsyncMock) as mock_dispatch:
        await tracker.check_anomaly(redis, "org-123", None, db, org)
    # Already fired this hour — should not fire again
    mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_no_alert_insufficient_baseline():
    """No alert when fewer than MIN_BASELINE_DAYS entries exist."""
    from app.services.cost_tracker import CostTrackerService

    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda k: b"30.00" if "rl:usd" in k else None)
    redis.zadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    # Only 2 days of data (< MIN_BASELINE_DAYS=3)
    redis.zrangebyscore = AsyncMock(return_value=[
        b"2026-03-09:1.0", b"2026-03-10:1.0",
    ])

    db = AsyncMock()
    org = MagicMock()
    org.settings = {}

    tracker = CostTrackerService()
    with patch("app.services.webhook_service.dispatch_event", new_callable=AsyncMock) as mock_dispatch:
        await tracker.check_anomaly(redis, "org-123", None, db, org)
    mock_dispatch.assert_not_called()
