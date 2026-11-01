"""Batched flush of request logs from Redis queue to PostgreSQL.

When BATCH_SPEND_ENABLED, audit_logger pushes log entries to rl:batch:queue
instead of writing directly to Postgres. This job flushes the queue every N seconds.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from uuid import UUID

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app import database
from app.config import settings
from app.models.request_log import RequestLog

logger = logging.getLogger(__name__)

BATCH_QUEUE_KEY = "rl:batch:queue"


def _serialize_log_entry(
    request_id: UUID,
    org_id: UUID,
    user_id: UUID,
    api_key_id: UUID | None,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: Decimal,
    latency_ms: int,
    ttft_ms: int | None,
    status_code: int,
    error_message: str | None,
    request_metadata: dict,
    provider_key_id: UUID | None = None,
) -> str:
    """Serialize a log entry for Redis. Decimal and UUID as strings."""
    return json.dumps({
        "request_id": str(request_id),
        "org_id": str(org_id),
        "user_id": str(user_id),
        "api_key_id": str(api_key_id) if api_key_id else None,
        "provider_key_id": str(provider_key_id) if provider_key_id else None,
        "model": model,
        "provider": provider,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": str(cost_usd),
        "latency_ms": latency_ms,
        "ttft_ms": ttft_ms,
        "status_code": status_code,
        "error_message": error_message,
        "request_metadata": request_metadata or {},
    })


def _deserialize_log_entry(raw: str) -> dict:
    """Deserialize a log entry from Redis."""
    data = json.loads(raw)
    return {
        "request_id": UUID(data["request_id"]),
        "org_id": UUID(data["org_id"]),
        "user_id": UUID(data["user_id"]),
        "api_key_id": UUID(data["api_key_id"]) if data.get("api_key_id") else None,
        "provider_key_id": UUID(data["provider_key_id"]) if data.get("provider_key_id") else None,
        "model": data["model"],
        "provider": data["provider"],
        "prompt_tokens": data["prompt_tokens"],
        "completion_tokens": data["completion_tokens"],
        "total_tokens": data["total_tokens"],
        "cost_usd": Decimal(data["cost_usd"]),
        "latency_ms": data["latency_ms"],
        "ttft_ms": data.get("ttft_ms"),
        "status_code": data["status_code"],
        "error_message": data.get("error_message"),
        "request_metadata": data.get("request_metadata") or {},
    }


async def push_to_batch_queue(redis: Redis, serialized: str) -> None:
    """Append a serialized log entry to the batch queue."""
    await redis.rpush(BATCH_QUEUE_KEY, serialized)


async def flush_request_logs_batch(redis: Redis) -> int:
    """Pop up to BATCH_SPEND_MAX_SIZE entries from the queue and bulk insert into Postgres.

    Returns the number of entries flushed.
    """
    if not settings.BATCH_SPEND_ENABLED:
        return 0

    max_size = settings.BATCH_SPEND_MAX_SIZE
    entries: list[dict] = []

    for _ in range(max_size):
        raw = await redis.lpop(BATCH_QUEUE_KEY)
        if raw is None:
            break
        try:
            entries.append(_deserialize_log_entry(raw))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Invalid batch queue entry, skipping: %s", e)
            continue

    if not entries:
        return 0

    # Entries can belong to several orgs; RLS WITH CHECK requires the matching org
    # to be set before each group's rows are flushed (set_config is transaction-local).
    by_org: dict[str, list[dict]] = {}
    for entry in entries:
        by_org.setdefault(str(entry["org_id"]), []).append(entry)

    try:
        async with database.AsyncSessionLocal() as db:
            for org_id, org_entries in by_org.items():
                await database.set_session_org_id(db, UUID(org_id))
                for entry in org_entries:
                    row = RequestLog(
                        request_id=entry["request_id"],
                        org_id=entry["org_id"],
                        user_id=entry["user_id"],
                        api_key_id=entry["api_key_id"],
                        provider_key_id=entry.get("provider_key_id"),
                        model=entry["model"],
                        provider=entry["provider"],
                        prompt_tokens=entry["prompt_tokens"],
                        completion_tokens=entry["completion_tokens"],
                        total_tokens=entry["total_tokens"],
                        cost_usd=entry["cost_usd"],
                        latency_ms=entry["latency_ms"],
                        ttft_ms=entry["ttft_ms"],
                        status_code=entry["status_code"],
                        error_message=entry["error_message"],
                        request_metadata=entry["request_metadata"],
                    )
                    db.add(row)
                await db.flush()
            await db.commit()
        logger.debug("Flushed %d request logs from batch queue", len(entries))
        return len(entries)
    except Exception:
        logger.exception("Failed to flush batch queue")
        for entry in entries:
            try:
                serialized = _serialize_log_entry(
                    entry["request_id"],
                    entry["org_id"],
                    entry["user_id"],
                    entry["api_key_id"],
                    entry["model"],
                    entry["provider"],
                    entry["prompt_tokens"],
                    entry["completion_tokens"],
                    entry["total_tokens"],
                    entry["cost_usd"],
                    entry["latency_ms"],
                    entry["ttft_ms"],
                    entry["status_code"],
                    entry["error_message"],
                    entry["request_metadata"],
                    provider_key_id=entry.get("provider_key_id"),
                )
                await redis.rpush(BATCH_QUEUE_KEY, serialized)
            except Exception:
                logger.error("Failed to re-queue entry after flush error")
        return 0


async def run_flush_request_logs_batch() -> None:
    """Scheduler job: flush batch queue to Postgres. Uses its own Redis connection."""
    if not settings.BATCH_SPEND_ENABLED:
        return
    redis = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )
    try:
        await flush_request_logs_batch(redis)
    finally:
        await redis.aclose()
