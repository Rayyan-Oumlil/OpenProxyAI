import { describe, expect, it } from "vitest";

import type { RequestLogDetail } from "../../api/types";
import { buildTrace } from "./trace";

function detail(overrides: Partial<RequestLogDetail> = {}): RequestLogDetail {
  return {
    id: "l1",
    created_at: "2026-11-03T10:00:00Z",
    model: "openai/gpt-4o-mini",
    provider: "openai",
    status: "success",
    prompt_tokens: 10,
    completion_tokens: 5,
    total_tokens: 15,
    cost_usd: 0.00001,
    latency_ms: 100,
    ttft_ms: null,
    error_message: null,
    policy_action: "allow",
    policy_reason: null,
    request_id: "r1",
    user_id: "u1",
    api_key_id: "k1",
    request_metadata: null,
    policy_triggered_rules: null,
    ...overrides,
  };
}

describe("buildTrace", () => {
  it("lays out stages as percentages of the request, in order", () => {
    const trace = buildTrace(
      detail({
        latency_ms: 100,
        request_metadata: {
          stages: [
            { name: "policy", start_ms: 0, ms: 10 },
            { name: "rate_limit", start_ms: 10, ms: 5 },
            { name: "upstream", start_ms: 20, ms: 80 },
          ],
        },
      }),
    );
    expect(trace.hasTimings).toBe(true);
    expect(trace.totalMs).toBe(100);
    expect(trace.stages.map((s) => s.label)).toEqual(["Policy checks", "Rate limit and budget", "Upstream call"]);
    expect(trace.stages[2].leftPct).toBeCloseTo(20);
    expect(trace.stages[2].widthPct).toBeCloseTo(80);
  });

  it("keeps a 0 ms stage visible and never lets a bar overflow the track", () => {
    const [instant, late] = buildTrace(
      detail({
        latency_ms: 100,
        request_metadata: {
          stages: [
            { name: "cache", start_ms: 3, ms: 0 },
            { name: "upstream", start_ms: 99, ms: 50 },
          ],
        },
      }),
    ).stages;
    expect(instant.widthPct).toBeGreaterThan(0);
    expect(late.leftPct + late.widthPct).toBeLessThanOrEqual(100);
  });

  it("grows the total to cover stages when the logged latency is shorter", () => {
    const trace = buildTrace(detail({ latency_ms: 10, request_metadata: { stages: [{ name: "upstream", start_ms: 0, ms: 40 }] } }));
    expect(trace.totalMs).toBe(40);
    expect(trace.stages[0].widthPct).toBeCloseTo(100);
  });

  it("reports rows without stage data as untimed instead of inventing bars", () => {
    expect(buildTrace(detail({ request_metadata: null })).hasTimings).toBe(false);
    expect(buildTrace(detail({ request_metadata: { cache: "miss" } })).stages).toEqual([]);
  });

  it("drops malformed stage entries", () => {
    const trace = buildTrace(
      detail({
        request_metadata: {
          stages: [
            "policy",
            null,
            { name: 5, start_ms: 0, ms: 1 },
            { name: "cache", start_ms: -1, ms: 1 },
            { name: "cache", start_ms: 0, ms: "fast" },
            { name: "upstream", start_ms: 0, ms: 12 },
          ],
        },
      }),
    );
    expect(trace.stages.map((s) => s.name)).toEqual(["upstream"]);
  });

  it("keeps unknown stage names as their own label", () => {
    expect(buildTrace(detail({ request_metadata: { stages: [{ name: "guardrail", start_ms: 0, ms: 1 }] } })).stages[0].label).toBe("guardrail");
  });

  it("reads cache tier, fallback and taint details, ignoring wrong types", () => {
    const trace = buildTrace(
      detail({
        request_metadata: { cache: "l2", fallback_count: 2, fallback_model_used: "openai/gpt-4o", tool_taint: { removed: ["a", 3, "b"] } },
      }),
    );
    expect(trace).toMatchObject({ cacheTier: "l2", fallbackCount: 2, fallbackModel: "openai/gpt-4o", taintRemoved: ["a", "b"] });
    const bad = buildTrace(detail({ request_metadata: { cache: 1, fallback_count: "x", tool_taint: [] } }));
    expect(bad).toMatchObject({ cacheTier: null, fallbackCount: 0, taintRemoved: [] });
  });

  it("labels the classification stage and reads the data class, ignoring malformed values", () => {
    const trace = buildTrace(
      detail({
        request_metadata: {
          stages: [{ name: "classify", start_ms: 0, ms: 1 }],
          data_class: { class: "confidential", source: "detected", entities: ["ssn", 4, "email"] },
        },
      }),
    );
    expect(trace.stages[0].label).toBe("Data classification");
    expect(trace.dataClass).toEqual({ name: "confidential", source: "detected", entities: ["ssn", "email"] });
    expect(buildTrace(detail({ request_metadata: {} })).dataClass).toBeNull();
    expect(buildTrace(detail({ request_metadata: { data_class: { class: 3 } } })).dataClass).toBeNull();
    expect(buildTrace(detail({ request_metadata: { data_class: [] } })).dataClass).toBeNull();
  });

  it("has no total when neither latency nor stages exist", () => {
    expect(buildTrace(detail({ latency_ms: null })).totalMs).toBeNull();
  });
});
