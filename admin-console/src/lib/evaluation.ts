import type { EvalRunStatus, EvaluatorType } from "../api/evaluationTypes";

export const STATUS_LABEL: Record<EvalRunStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
  budget_exceeded: "Stopped at cost cap",
};

export const STATUS_VARIANT: Record<EvalRunStatus, "success" | "warning" | "error" | "muted" | "policy"> = {
  queued: "muted",
  running: "policy",
  completed: "success",
  failed: "error",
  cancelled: "muted",
  budget_exceeded: "warning",
};

export const EVALUATOR_LABEL: Record<EvaluatorType, string> = {
  exact: "Exact match",
  regex: "Regular expression",
  llm_judge: "LLM judge",
};

export const EVALUATOR_HELP: Record<EvaluatorType, string> = {
  exact: "The answer must equal the item's expected answer.",
  regex: "The answer must match a pattern. Runs with a one-second timeout.",
  llm_judge: "Another model grades each answer against criteria you write.",
};

/** 0.8333 -> "83%". A missing value is a dash, never "0%": an unscored run has no rate, which is not the same as failing. */
export function percent(value: number | null | undefined): string {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

export function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return value >= 0.01 ? `$${value.toFixed(2)}` : `$${value.toFixed(4)}`;
}

/** The first user message of an item, for a one-line preview. */
export function previewOf(messages: Array<{ role: string; content: unknown }>, limit = 90): string {
  const first = messages.find((m) => m.role === "user") ?? messages[0];
  const text = typeof first?.content === "string" ? first.content : "[non-text content]";
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

/** An ISO string from a datetime-local input ("2026-11-10T09:30"), read as the browser's local time. */
export function toIso(local: string): string | undefined {
  if (!local) return undefined;
  const date = new Date(local);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

/** Whole seconds between two ISO timestamps, or null while a run has not finished. */
export function durationSeconds(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;
  return Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000));
}
