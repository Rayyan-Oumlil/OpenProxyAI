"""
ClickHouse dual-write service for high-volume request log analytics.
Off by default — enable by setting CLICKHOUSE_URL.
Lazy-init singleton — safe to import always.
All operations are fire-and-forget; exceptions never propagate to caller.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

_client = None
_initialized = False


def _get_client():
    global _client, _initialized
    if _initialized:
        return _client
    _initialized = True
    from app.config import settings
    if not settings.CLICKHOUSE_URL:
        logger.debug("CLICKHOUSE_URL not set — ClickHouse dual-write disabled")
        return None
    try:
        import clickhouse_connect
        _client = clickhouse_connect.get_client(dsn=settings.CLICKHOUSE_URL)
        logger.info("ClickHouse client initialized: %s", settings.CLICKHOUSE_URL)
    except ImportError:
        logger.warning("clickhouse-connect not installed — ClickHouse disabled")
        _client = None
    except Exception as exc:
        logger.warning("ClickHouse init failed: %s", exc)
        _client = None
    return _client


def is_enabled() -> bool:
    return _get_client() is not None


async def write_log(log_data: dict) -> None:
    """
    Write a single request log entry to ClickHouse.
    Fire-and-forget — all exceptions are swallowed.
    log_data keys: request_id, org_id, user_id, api_key_id, model, provider,
                   prompt_tokens, completion_tokens, total_tokens, cost_usd,
                   latency_ms, ttft_ms, status_code, policy_action, created_at
    """
    client = _get_client()
    if client is None:
        return
    try:
        from app.config import settings
        row = [
            str(log_data.get("request_id", "")),
            str(log_data.get("org_id", "")),
            str(log_data.get("user_id", "")),
            str(log_data.get("api_key_id", "")),
            str(log_data.get("model", "")),
            str(log_data.get("provider", "")),
            int(log_data.get("prompt_tokens", 0)),
            int(log_data.get("completion_tokens", 0)),
            int(log_data.get("total_tokens", 0)),
            float(log_data.get("cost_usd", 0.0)),
            int(log_data.get("latency_ms", 0)),
            int(log_data.get("ttft_ms", 0)),
            int(log_data.get("status_code", 200)),
            str(log_data.get("policy_action", "")),
            log_data.get("created_at"),
        ]
        client.insert(
            f"{settings.CLICKHOUSE_DATABASE}.request_logs_ch",
            [row],
            column_names=[
                "request_id", "org_id", "user_id", "api_key_id",
                "model", "provider", "prompt_tokens", "completion_tokens",
                "total_tokens", "cost_usd", "latency_ms", "ttft_ms",
                "status_code", "policy_action", "created_at",
            ],
        )
    except Exception as exc:
        logger.warning("ClickHouse write_log failed: %s", exc)
