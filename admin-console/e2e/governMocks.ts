/** API fixtures for the plugin, analytics query and scores screens. */

export const PLUGIN = { id: "p1", name: "no-codenames", sha256: "a".repeat(64), size_bytes: 214, enabled: true, created_at: "2026-11-01T10:00:00Z" };

export const BATCH_JOBS = [
  { id: "b1", status: "in_progress", created_by: "ana@example.com", total: 40, completed: 12, failed: 1, cost_usd: 0.31, max_cost_usd: 5, error: null, created_at: "2026-11-02T09:00:00Z", finished_at: null },
  { id: "b2", status: "budget_exceeded", created_by: "lee@example.com", total: 100, completed: 60, failed: 0, cost_usd: 5, max_cost_usd: 5, error: "The spending cap was reached.", created_at: "2026-11-01T09:00:00Z", finished_at: "2026-11-01T09:20:00Z" },
];

export const CATALOG = {
  views: [
    { name: "requests", columns: { model: "text", cost_usd: "number", status_code: "int", created_at: "time", day: "time" } },
    { name: "scores", columns: { score_name: "text", value: "number" } },
  ],
  aggregates: ["count", "sum", "avg", "min", "max", "p50", "p95"],
  operators: ["=", "!=", ">", ">=", "<", "<=", "in"],
};

export const QUERY_RESULT = { columns: ["model", "count"], rows: [["openai/gpt-4o", 4], ["openai/gpt-4o-mini", 9]], row_count: 2, truncated: false };

export const SCORE_SUMMARY = { group_by: "score_name", groups: [{ group: "thumbs", count: 12, mean: 0.75, min: 0, max: 1 }] };
export const SCORES = [
  { id: "s1", request_id: "r1", score_name: "thumbs", value: 1, source: "api", comment: "loved it", model: "openai/gpt-4o", created_at: "2026-11-01T10:00:00Z" },
];

export function governMock(pathname: string, method: string): unknown | undefined {
  if (pathname === "/api/v1/policy-plugins") return [PLUGIN];
  if (pathname === "/api/v1/batch-jobs") return BATCH_JOBS;
  if (pathname === "/api/v1/analytics/query/catalog") return CATALOG;
  if (pathname === "/api/v1/analytics/query" && method === "POST") return QUERY_RESULT;
  if (pathname === "/api/v1/scores/summary") return SCORE_SUMMARY;
  if (pathname === "/api/v1/scores") return SCORES;
  return undefined;
}
