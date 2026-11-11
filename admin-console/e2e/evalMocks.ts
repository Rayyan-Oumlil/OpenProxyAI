/** API fixtures for the evaluation screens (datasets, evaluators, eval runs, adaptive experiments, prompt promotion). */

export const DATASET = { id: "d1", name: "support-regressions", description: "Tickets that once went wrong", item_count: 3, created_at: "2026-11-01T10:00:00Z" };

export const DATASET_ITEMS = [
  { id: "i1", request_id: "r1", messages: [{ role: "user", content: "How do I reset my password?" }], output: "Use the reset link.", expected: null, created_at: "2026-11-01T10:00:00Z" },
  { id: "i2", request_id: null, messages: [{ role: "user", content: "What is the capital of France?" }], output: null, expected: "Paris", created_at: "2026-11-01T10:00:00Z" },
];

export const EVALUATORS = [
  { id: "e1", name: "exact-match", type: "exact", config: { case_sensitive: false, strip: true }, created_at: "2026-11-01T10:00:00Z" },
  { id: "e2", name: "helpful-judge", type: "llm_judge", config: { model: "openai/gpt-4o-mini", criteria: "Is it helpful?", scale: "1-5", pass_threshold: 4 }, created_at: "2026-11-01T10:00:00Z" },
];

const RUN_BASE = {
  dataset_id: "d1", evaluator_id: "e1", evaluator: { name: "exact-match", type: "exact", config: {} }, prompt_template_id: null, candidate_model: "openai/gpt-4o-mini",
  error: null, created_at: "2026-11-03T10:00:00Z", started_at: "2026-11-03T10:00:01Z",
};

export const EVAL_RUNS = [
  { ...RUN_BASE, id: "r1", status: "completed", total_items: 20, completed_items: 20, scored_items: 18, failed_items: 2, passed_items: 15, mean_score: 0.83, pass_rate: 0.83, cost_usd: 0.12, max_cost_usd: 1, finished_at: "2026-11-03T10:00:41Z" },
  { ...RUN_BASE, id: "r2", status: "running", total_items: 50, completed_items: 12, scored_items: 12, failed_items: 0, passed_items: 9, mean_score: 0.75, pass_rate: 0.75, cost_usd: 0.03, max_cost_usd: 1, finished_at: null },
];

export const EVAL_RUN_ITEMS = [
  { id: "a", dataset_item_id: "i1", output: "Use the reset link.", score: 1, passed: true, reason: "matches the expected answer", error: null, cost_usd: 0.001, latency_ms: 120 },
  { id: "b", dataset_item_id: "i2", output: "Lyon", score: 0, passed: false, reason: "expected 'Paris', got 'Lyon'", error: null, cost_usd: 0.001, latency_ms: 90 },
  { id: "c", dataset_item_id: "i3", output: null, score: null, passed: null, reason: null, error: "Blocked by policy.", cost_usd: 0, latency_ms: 4 },
];

export const DRAFT_TEMPLATE = {
  id: "t2", org_id: "o1", name: "support-agent", description: "Answers support questions", system_message: "You are a very concise support agent.",
  user_template: "{{question}}", variables_schema: [], version: 2, is_active: false, status: "draft", created_by: "u1",
  created_at: "2026-11-03T10:00:00Z", updated_at: "2026-11-03T10:00:00Z",
};

export const PROMOTION_STATUS = {
  template_id: "t2", name: "support-agent", version: 2, status: "draft", gate_enabled: true, requirements: { min_pass_rate: 0.8, min_items: 10 },
  passes_gate: false, qualifying_run: null,
  best_run: { run_id: "r1", status: "completed", total_items: 20, scored_items: 18, failed_items: 2, pass_rate: 0.6, mean_score: 0.6 },
  reasons: ["the pass rate was 60%; at least 80% is required", "2 of 20 items could not be scored"],
};

export const ADAPTIVE_EXPERIMENT = {
  id: "x1", org_id: "o1", name: "mini vs full", target_model: "openai/gpt-4o", is_active: true, created_at: "2026-11-02T10:00:00Z",
  variants: [
    { id: "v1", experiment_id: "x1", model: "openai/gpt-4o-mini", traffic_weight: 35 },
    { id: "v2", experiment_id: "x1", model: "openai/gpt-4o", traffic_weight: 65 },
  ],
  mode: "adaptive", metric: "thumbs", min_samples_per_variant: 30, delta: 0.01, weight_floor: 5, winner_variant_id: null, stopped_reason: null, adaptive_error: null,
};

export const ADAPTIVE_RESULTS = {
  variants: [
    { variant_id: "v1", model: "openai/gpt-4o-mini", traffic_weight: 35, probability_best: 0.31, request_count: 120, avg_latency_ms: 410, total_cost_usd: 0.42, total_prompt_tokens: 900, total_completion_tokens: 600, policy_violations: 0, scores: [{ name: "thumbs", avg: 0.62, count: 48 }] },
    { variant_id: "v2", model: "openai/gpt-4o", traffic_weight: 65, probability_best: 0.69, request_count: 140, avg_latency_ms: 650, total_cost_usd: 1.9, total_prompt_tokens: 1000, total_completion_tokens: 700, policy_violations: 0, scores: [{ name: "thumbs", avg: 0.7, count: 52 }] },
  ],
  adaptive: { metric: "thumbs", ready: true, min_samples_per_variant: 30, delta: 0.01, samples: { v1: 48, v2: 52 }, winner_variant_id: null, stopped_reason: null, error: null },
};

/** Returns a response for an evaluation endpoint, or undefined when the path is not one of them. */
export function evalMock(pathname: string, method: string): unknown | undefined {
  if (pathname === "/api/v1/datasets") return [DATASET];
  if (pathname === "/api/v1/datasets/d1/items") return DATASET_ITEMS;
  if (pathname === "/api/v1/datasets/d1/import" && method === "POST") return { imported: 4, skipped_redacted: 1, skipped_duplicate: 0, stopped_at_capacity: false };
  if (pathname === "/api/v1/evaluators") return EVALUATORS;
  if (pathname === "/api/v1/eval-runs") return EVAL_RUNS;
  if (pathname === "/api/v1/eval-runs/r1/items") return EVAL_RUN_ITEMS;
  if (pathname === "/api/v1/prompt-templates") return [DRAFT_TEMPLATE];
  if (pathname === "/api/v1/prompt-templates/t2/promotion") return PROMOTION_STATUS;
  if (pathname === "/api/v1/experiments") return [ADAPTIVE_EXPERIMENT];
  if (pathname === "/api/v1/experiments/x1/results") return ADAPTIVE_RESULTS;
  return undefined;
}
