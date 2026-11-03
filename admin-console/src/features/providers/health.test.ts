import { describe, expect, it } from "vitest";

import type { ProviderKeyResponse } from "../../api/types";
import { keyState, lacksAdaptiveData, neverChecked, summarize } from "./health";

const NOW = 1_700_000_000_000;

function key(overrides: Partial<ProviderKeyResponse> = {}): ProviderKeyResponse {
  return {
    id: "k1",
    provider: "openai",
    alias: null,
    key_alias: "primary",
    key_prefix: "sk-abc123…",
    weight: 1,
    is_active: true,
    region: "us",
    model_patterns: null,
    created_at: "2026-11-01T10:00:00Z",
    ...overrides,
  };
}

describe("keyState", () => {
  it("ranks the worst signal first", () => {
    const open = NOW / 1000 + 60;
    expect(keyState(key({ is_active: false, circuit_open_until: open }), NOW).health).toBe("disabled");
    expect(keyState(key({ circuit_open_until: open, health_status: "healthy" }), NOW).health).toBe("down");
    expect(keyState(key({ health_status: "unhealthy", consecutive_failures: 3 }), NOW).health).toBe("down");
    expect(keyState(key({ health_status: "healthy", error_rate: 0.4 }), NOW).health).toBe("degraded");
  });

  it("treats an expired circuit as closed", () => {
    expect(keyState(key({ circuit_open_until: NOW / 1000 - 1, health_status: "healthy" }), NOW).health).toBe("healthy");
  });

  it("flags the error-rate threshold exactly and not below it", () => {
    expect(keyState(key({ error_rate: 0.1 }), NOW).health).toBe("degraded");
    expect(keyState(key({ error_rate: 0.099 }), NOW).health).toBe("healthy");
  });

  it("degrades on failed checks that have not yet reached the unhealthy threshold", () => {
    const state = keyState(key({ health_status: "unknown", consecutive_failures: 2 }), NOW);
    expect(state.health).toBe("degraded");
    expect(state.reason).toContain("2 failed");
  });

  it("is healthy after a passed check, or when recent traffic succeeds", () => {
    expect(keyState(key({ health_status: "healthy" }), NOW).health).toBe("healthy");
    expect(keyState(key({ error_rate: 0, latency_p99_ms: 120 }), NOW).health).toBe("healthy");
  });

  it("is unknown, not healthy, when nothing has been measured", () => {
    const state = keyState(key(), NOW);
    expect(state.health).toBe("unknown");
    expect(state.verdict).toBe("neutral");
  });

  it("maps states onto the badge verdicts", () => {
    expect(keyState(key({ health_status: "healthy" }), NOW).verdict).toBe("allowed");
    expect(keyState(key({ error_rate: 0.5 }), NOW).verdict).toBe("flagged");
    expect(keyState(key({ health_status: "unhealthy" }), NOW).verdict).toBe("blocked");
  });
});

describe("summaries", () => {
  it("counts keys per state", () => {
    const keys = [
      key({ id: "a", health_status: "healthy" }),
      key({ id: "b", health_status: "healthy" }),
      key({ id: "c", health_status: "unhealthy" }),
      key({ id: "d", is_active: false }),
      key({ id: "e" }),
    ];
    expect(summarize(keys, NOW)).toEqual({ healthy: 2, degraded: 0, down: 1, unknown: 1, disabled: 1 });
  });

  it("detects missing adaptive data and never-checked fleets, and is false for an empty list", () => {
    expect(lacksAdaptiveData([key()])).toBe(true);
    expect(lacksAdaptiveData([key(), key({ latency_p99_ms: 90 })])).toBe(false);
    expect(lacksAdaptiveData([])).toBe(false);
    expect(neverChecked([key()])).toBe(true);
    expect(neverChecked([key({ last_health_check_at: "2026-11-03T10:00:00Z" })])).toBe(false);
    expect(neverChecked([])).toBe(false);
  });
});
