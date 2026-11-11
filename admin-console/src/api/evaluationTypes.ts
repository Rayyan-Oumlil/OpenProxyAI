/** Shapes of the eval-loop API (datasets, evaluators, eval runs, promotion). Mirrors backend/app/schemas/. */

export type Dataset = {
  id: string;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string;
};

export type DatasetItemMessage = { role: "system" | "user" | "assistant"; content: string };

export type DatasetItem = {
  id: string;
  request_id: string | null;
  messages: Array<{ role: string; content: unknown }>;
  output: string | null;
  expected: string | null;
  created_at: string;
};

export type ImportRequest = {
  model?: string;
  since?: string;
  until?: string;
  score_name?: string;
  min_score?: number;
  max_score?: number;
  limit?: number;
  order?: "latest" | "random";
};

export type ImportResponse = {
  imported: number;
  skipped_redacted: number;
  skipped_duplicate: number;
  stopped_at_capacity: boolean;
};

export type EvaluatorType = "exact" | "regex" | "llm_judge";

export type Evaluator = {
  id: string;
  name: string;
  type: EvaluatorType;
  config: Record<string, unknown>;
  created_at: string;
};

export type EvalRunStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "budget_exceeded";

export type EvalRun = {
  id: string;
  dataset_id: string | null;
  evaluator_id: string | null;
  evaluator: { name: string; type: EvaluatorType; config: Record<string, unknown> };
  prompt_template_id: string | null;
  candidate_model: string;
  status: EvalRunStatus;
  total_items: number;
  completed_items: number;
  scored_items: number;
  failed_items: number;
  passed_items: number;
  mean_score: number | null;
  pass_rate: number | null;
  cost_usd: number;
  max_cost_usd: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type EvalRunItem = {
  id: string;
  dataset_item_id: string | null;
  output: string | null;
  score: number | null;
  passed: boolean | null;
  reason: string | null;
  error: string | null;
  cost_usd: number;
  latency_ms: number | null;
};

export type CreateEvalRunRequest = {
  dataset_id: string;
  evaluator_id: string;
  candidate_model: string;
  system_prompt?: string;
  prompt_template_id?: string;
  max_items?: number;
  max_cost_usd?: number;
};

export type RunSummary = {
  run_id: string;
  status: string;
  total_items: number;
  scored_items: number;
  failed_items: number;
  pass_rate: number | null;
  mean_score: number | null;
};

export type PromotionStatus = {
  template_id: string;
  name: string;
  version: number;
  status: "draft" | "active" | "retired";
  gate_enabled: boolean;
  requirements: { min_pass_rate: number; min_items: number };
  passes_gate: boolean;
  qualifying_run: RunSummary | null;
  best_run: RunSummary | null;
  reasons: string[];
};

export type PromoteResponse = {
  template_id: string;
  name: string;
  version: number;
  status: string;
  previous_version: number | null;
  run_id: string | null;
  overridden: boolean;
};

export const ACTIVE_RUN_STATUSES: EvalRunStatus[] = ["queued", "running"];

export function isRunActive(status: EvalRunStatus): boolean {
  return ACTIVE_RUN_STATUSES.includes(status);
}
