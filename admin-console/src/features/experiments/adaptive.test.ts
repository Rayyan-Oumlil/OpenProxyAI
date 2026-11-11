import { describe, expect, it } from "vitest";

import type { AdaptiveStatus, ExperimentResponse, VariantMetrics } from "../../api/types";
import { chanceLabel, ratingsStillNeeded, resultKey, samplesByModel, variantsChanged, winnerOf } from "./adaptive";

const status = (overrides: Partial<AdaptiveStatus> = {}): AdaptiveStatus => ({
  metric: "thumbs", ready: false, min_samples_per_variant: 30, delta: 0.01, samples: {}, winner_variant_id: null, stopped_reason: null, error: null, ...overrides,
});

const experiment = (overrides: Partial<ExperimentResponse> = {}): ExperimentResponse =>
  ({
    id: "e1", org_id: "o", name: "x", target_model: "gpt-4o", is_active: true, created_at: "",
    variants: [{ id: "v1", experiment_id: "e1", model: "mini", traffic_weight: 50 }, { id: "v2", experiment_id: "e1", model: "full", traffic_weight: 50 }],
    ...overrides,
  }) as ExperimentResponse;

describe("chanceLabel", () => {
  it("never shows a certainty it does not have", () => {
    expect(chanceLabel(0.9731)).toBe("97%");
    expect(chanceLabel(0.004)).toBe("<1%");
    expect(chanceLabel(0.9996)).toBe(">99%");
    expect(chanceLabel(0)).toBe("0%");
    expect(chanceLabel(1)).toBe("100%");
    expect(chanceLabel(null)).toBe("—");
    expect(chanceLabel(undefined)).toBe("—");
  });
});

describe("ratingsStillNeeded", () => {
  it("is set by the slowest variant", () => {
    expect(ratingsStillNeeded(status({ samples: { a: 22, b: 5 } }))).toBe(25);
    expect(ratingsStillNeeded(status({ samples: { a: 40, b: 31 } }))).toBe(0);
  });
  it("is the whole minimum when nothing has been rated", () => {
    expect(ratingsStillNeeded(status())).toBe(30);
  });
});

describe("samplesByModel", () => {
  it("counts a variant with no ratings as zero", () => {
    expect(samplesByModel(experiment(), status({ samples: { v1: 12 } }))).toEqual([{ model: "mini", n: 12 }, { model: "full", n: 0 }]);
  });
});

describe("winnerOf", () => {
  it("finds the variant that won, and nothing when none did", () => {
    expect(winnerOf(experiment({ winner_variant_id: "v2" }))?.model).toBe("full");
    expect(winnerOf(experiment())).toBeUndefined();
    expect(winnerOf(experiment({ winner_variant_id: "gone" }))).toBeUndefined();
  });
});

describe("resultKey", () => {
  it("keeps two variants on the same model apart", () => {
    const a = { model: "mini", variant_id: "v1" } as VariantMetrics;
    const b = { model: "mini", variant_id: "v2" } as VariantMetrics;
    expect(resultKey(a, 0)).not.toBe(resultKey(b, 1));
  });
  it("falls back to model and position for rows logged before variants had ids", () => {
    const old = { model: "mini" } as VariantMetrics;
    expect(resultKey(old, 0)).not.toBe(resultKey(old, 1));
  });
});

describe("variantsChanged", () => {
  const base = [{ model: "a", traffic_weight: 50 }, { model: "b", traffic_weight: 50 }];
  it("is false for the same variants, so an edit of the name does not replace them", () => {
    expect(variantsChanged(base, [...base.map((v) => ({ ...v }))])).toBe(false);
  });
  it("sees a changed model, weight or count", () => {
    expect(variantsChanged(base, [{ model: "a", traffic_weight: 50 }, { model: "c", traffic_weight: 50 }])).toBe(true);
    expect(variantsChanged(base, [{ model: "a", traffic_weight: 60 }, { model: "b", traffic_weight: 50 }])).toBe(true);
    expect(variantsChanged(base, [base[0]])).toBe(true);
  });
});
