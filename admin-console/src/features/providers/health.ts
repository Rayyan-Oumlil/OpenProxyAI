import type { ProviderKeyResponse } from "../../api/types";
import type { Verdict } from "../../components/ui/StatusBadge";

export type KeyHealth = "healthy" | "degraded" | "down" | "unknown" | "disabled";

export interface KeyState {
  health: KeyHealth;
  verdict: Verdict;
  label: string;
  /** Why the key is in this state, in words an operator can act on. */
  reason: string;
}

/** An error rate at or above this share of recent requests marks a key as degraded. */
export const DEGRADED_ERROR_RATE = 0.1;

const VERDICT: Record<KeyHealth, Verdict> = {
  healthy: "allowed",
  degraded: "flagged",
  down: "blocked",
  unknown: "neutral",
  disabled: "neutral",
};

const LABEL: Record<KeyHealth, string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  down: "Down",
  unknown: "Not checked",
  disabled: "Disabled",
};

function state(health: KeyHealth, reason: string): KeyState {
  return { health, verdict: VERDICT[health], label: LABEL[health], reason };
}

/**
 * One state per key, worst signal first: disabled, circuit open, failed health checks, high error rate,
 * recent failures, then healthy. `nowMs` is passed in so the result is a pure function of the data.
 */
export function keyState(key: ProviderKeyResponse, nowMs: number): KeyState {
  if (!key.is_active) return state("disabled", "Turned off, receives no traffic.");
  if (key.circuit_open_until != null && key.circuit_open_until * 1000 > nowMs) {
    return state("down", "Circuit breaker is open after repeated failures; traffic is routed to other keys.");
  }
  if (key.health_status === "unhealthy") {
    return state("down", `Failed ${key.consecutive_failures ?? 0} health checks in a row.`);
  }
  if (key.error_rate != null && key.error_rate >= DEGRADED_ERROR_RATE) {
    return state("degraded", "High error rate on recent requests.");
  }
  if ((key.consecutive_failures ?? 0) > 0) {
    return state("degraded", `${key.consecutive_failures} failed health check(s) since the last success.`);
  }
  if (key.health_status === "healthy") return state("healthy", "Last health check passed.");
  if (key.error_rate != null || key.latency_p99_ms != null) return state("healthy", "Recent requests are succeeding.");
  return state("unknown", "No health check or traffic data yet.");
}

export interface HealthSummary {
  healthy: number;
  degraded: number;
  down: number;
  unknown: number;
  disabled: number;
}

export function summarize(keys: ProviderKeyResponse[], nowMs: number): HealthSummary {
  const summary: HealthSummary = { healthy: 0, degraded: 0, down: 0, unknown: 0, disabled: 0 };
  for (const key of keys) summary[keyState(key, nowMs).health] += 1;
  return summary;
}

/** True when no key reports latency or error data, i.e. adaptive load balancing is off or has seen no traffic. */
export function lacksAdaptiveData(keys: ProviderKeyResponse[]): boolean {
  return keys.length > 0 && keys.every((k) => k.latency_p99_ms == null && k.error_rate == null);
}

/** True when no key has ever been health-checked. */
export function neverChecked(keys: ProviderKeyResponse[]): boolean {
  return keys.length > 0 && keys.every((k) => !k.last_health_check_at);
}
