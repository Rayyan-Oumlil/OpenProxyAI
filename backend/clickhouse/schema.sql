-- ClickHouse schema for OpenProxyAI request logs
-- Engine: ReplacingMergeTree (idempotent re-inserts on deduplication)
-- Partition by month for efficient pruning

CREATE DATABASE IF NOT EXISTS openproxy;

CREATE TABLE IF NOT EXISTS openproxy.request_logs_ch (
    request_id   UUID,
    org_id       UUID,
    user_id      UUID,
    api_key_id   UUID,
    model        String,
    provider     LowCardinality(String),
    prompt_tokens UInt32,
    completion_tokens UInt32,
    total_tokens  UInt32,
    cost_usd      Decimal(10, 6),
    latency_ms    UInt32,
    ttft_ms       UInt32,
    status_code   UInt16,
    policy_action LowCardinality(String),
    created_at   DateTime
) ENGINE = ReplacingMergeTree()
  ORDER BY (org_id, toDate(created_at), request_id)
  PARTITION BY toYYYYMM(created_at);

-- Useful materialized view for daily analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS openproxy.mv_daily_spend_ch
ENGINE = SummingMergeTree()
ORDER BY (org_id, day, model)
AS SELECT
    org_id,
    toDate(created_at) AS day,
    model,
    sum(prompt_tokens) AS prompt_tokens,
    sum(completion_tokens) AS completion_tokens,
    sum(total_tokens) AS total_tokens,
    sum(cost_usd) AS cost_usd,
    count() AS request_count
FROM openproxy.request_logs_ch
GROUP BY org_id, day, model;
