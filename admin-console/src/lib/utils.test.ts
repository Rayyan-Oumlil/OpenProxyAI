import { describe, expect, it } from "vitest";

import { formatAxisCost, formatCompact, formatCost, formatLatency, formatNumber, formatPercent } from "./utils";

const DASH = "—";

describe("formatNumber", () => {
  it("keeps exact counts below a million and separates thousands", () => {
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber(999)).toBe("999");
    expect(formatNumber(12_345)).toBe("12,345");
    expect(formatNumber(999_999)).toBe("999,999");
  });

  it("abbreviates millions and up", () => {
    expect(formatNumber(1_000_000)).toBe("1M");
    expect(formatNumber(2_450_000)).toBe("2.5M");
    expect(formatNumber(3_100_000_000)).toBe("3.1B");
  });

  it("shows a dash instead of NaN or Infinity", () => {
    expect(formatNumber(Number.NaN)).toBe(DASH);
    expect(formatNumber(Number.POSITIVE_INFINITY)).toBe(DASH);
  });
});

describe("formatCompact", () => {
  it("is short enough for an axis", () => {
    expect(formatCompact(950)).toBe("950");
    expect(formatCompact(1_200)).toBe("1.2K");
    expect(formatCompact(3_000_000)).toBe("3M");
  });
});

describe("formatCost", () => {
  it("uses whole cents with separators from one dollar up", () => {
    expect(formatCost(0)).toBe("$0.00");
    expect(formatCost(1)).toBe("$1.00");
    expect(formatCost(2000)).toBe("$2,000.00");
    expect(formatCost(1_234_567.891)).toBe("$1,234,567.89");
  });

  it("keeps a single request's cost visible instead of rounding it away", () => {
    expect(formatCost(0.0042)).toBe("$0.0042");
    expect(formatCost(0.000031)).toBe("$0.000031");
  });

  it("handles negatives and bad input", () => {
    expect(formatCost(-12.5)).toBe("-$12.50");
    expect(formatCost(-0.0042)).toBe("-$0.0042");
    expect(formatCost(Number.NaN)).toBe(DASH);
  });
});

describe("formatAxisCost", () => {
  it("never produces the old $2000.000 ticks", () => {
    expect(formatAxisCost(2000)).toBe("$2K");
    expect(formatAxisCost(2500)).toBe("$2.5K");
    expect(formatAxisCost(12)).toBe("$12");
    expect(formatAxisCost(1.5)).toBe("$1.5");
    expect(formatAxisCost(0.0035)).toBe("$0.0035");
    expect(formatAxisCost(0.5)).toBe("$0.5");
    expect(formatAxisCost(0)).toBe("$0");
  });
});

describe("formatPercent", () => {
  it("turns a ratio into a percentage", () => {
    expect(formatPercent(0.982)).toBe("98.2%");
    expect(formatPercent(1, 0)).toBe("100%");
    expect(formatPercent(Number.NaN)).toBe(DASH);
  });
});

describe("formatLatency", () => {
  it("scales from milliseconds to minutes", () => {
    expect(formatLatency(42.4)).toBe("42ms");
    expect(formatLatency(1500)).toBe("1.5s");
    expect(formatLatency(60_000)).toBe("1m");
    expect(formatLatency(95_000)).toBe("1m 35s");
    expect(formatLatency(Number.NaN)).toBe(DASH);
  });
});
