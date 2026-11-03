import { describe, expect, it } from "vitest";

import { burndown, canCompare, change, fillDays, shiftDay, splitPeriods, totals, type Day } from "./metrics";

function day(date: string, requests = 0, cost = 0, latency = 0, tokens = 0): Day {
  return { date, requests, tokens, cost_usd: cost, avg_latency_ms: latency };
}

describe("shiftDay", () => {
  it("moves across month and year boundaries and leap days", () => {
    expect(shiftDay("2026-11-01", -1)).toBe("2026-10-31");
    expect(shiftDay("2026-12-31", 1)).toBe("2027-01-01");
    expect(shiftDay("2028-02-28", 1)).toBe("2028-02-29");
    expect(shiftDay("2026-03-01", -1)).toBe("2026-02-28");
  });
});

describe("fillDays", () => {
  it("returns exactly N consecutive days ending at the end day, zero-filling gaps", () => {
    const filled = fillDays([day("2026-11-03", 5), day("2026-11-01", 2)], "2026-11-03", 4);
    expect(filled.map((d) => d.date)).toEqual(["2026-10-31", "2026-11-01", "2026-11-02", "2026-11-03"]);
    expect(filled.map((d) => d.requests)).toEqual([0, 2, 0, 5]);
  });

  it("ignores backend days outside the window", () => {
    expect(fillDays([day("2026-10-01", 99)], "2026-11-03", 3).every((d) => d.requests === 0)).toBe(true);
  });
});

describe("totals", () => {
  it("sums requests, tokens and cost and weights latency by requests", () => {
    const t = totals([day("a", 1, 0.5, 100, 10), day("b", 9, 1.5, 200, 90)]);
    expect(t).toMatchObject({ requests: 10, tokens: 100, cost: 2 });
    expect(t.avgLatencyMs).toBeCloseTo(190); // (1*100 + 9*200) / 10, not the plain mean of 150
  });

  it("is all zeros for an empty period, not NaN", () => {
    expect(totals([day("a"), day("b")])).toEqual({ requests: 0, tokens: 0, cost: 0, avgLatencyMs: 0 });
  });
});

describe("splitPeriods", () => {
  const trend = [day("2026-11-03", 10), day("2026-11-02", 10), day("2026-10-30", 4), day("2026-10-29", 6)];

  it("splits a 2N window into the current period and the one before", () => {
    const { current, previous } = splitPeriods(trend, "2026-11-03", 2, true);
    expect(current.map((d) => d.date)).toEqual(["2026-11-02", "2026-11-03"]);
    expect(totals(current).requests).toBe(20);
    expect(previous?.map((d) => d.date)).toEqual(["2026-10-31", "2026-11-01"]);
    expect(totals(previous ?? []).requests).toBe(0);
  });

  it("gives no previous period when comparison is off", () => {
    const { current, previous } = splitPeriods(trend, "2026-11-03", 2, false);
    expect(current).toHaveLength(2);
    expect(previous).toBeNull();
  });
});

describe("canCompare", () => {
  it("allows windows whose double fits the 90-day cap", () => {
    expect(canCompare(7)).toBe(true);
    expect(canCompare(30)).toBe(true);
    expect(canCompare(45)).toBe(true);
    expect(canCompare(90)).toBe(false);
  });
});

describe("change", () => {
  it("is the relative change as a fraction", () => {
    expect(change(150, 100)).toBeCloseTo(0.5);
    expect(change(50, 100)).toBeCloseTo(-0.5);
    expect(change(100, 100)).toBe(0);
  });

  it("is null, never Infinity or NaN, when there is nothing to compare", () => {
    expect(change(10, 0)).toBeNull();
    expect(change(10, null)).toBeNull();
    expect(change(10, undefined)).toBeNull();
    expect(change(10, Number.NaN)).toBeNull();
  });
});

describe("burndown", () => {
  it("accumulates spend per day of the month and projects the month total", () => {
    const b = burndown([day("2026-11-01", 1, 10), day("2026-11-03", 1, 20)], "2026-11-03", 300);
    expect(b.spent).toEqual([10, 10, 30]);
    expect(b.spentToDate).toBe(30);
    expect(b.daysInMonth).toBe(30);
    expect(b.projected).toBeCloseTo(300); // 30 / 3 days * 30 days
    expect(b.budgetUsed).toBeCloseTo(0.1);
  });

  it("ignores days from the previous month", () => {
    const b = burndown([day("2026-10-31", 1, 999), day("2026-11-02", 1, 5)], "2026-11-02", null);
    expect(b.spent).toEqual([0, 5]);
  });

  it("has no budget figures without a valid budget", () => {
    for (const budget of [null, 0, -5, Number.NaN]) {
      const b = burndown([day("2026-11-01", 1, 10)], "2026-11-01", budget);
      expect(b.budget).toBeNull();
      expect(b.budgetUsed).toBeNull();
    }
  });

  it("knows the length of February in a leap year", () => {
    expect(burndown([], "2028-02-10", null).daysInMonth).toBe(29);
    expect(burndown([], "2026-02-10", null).daysInMonth).toBe(28);
  });

  it("flags a budget that is already exceeded", () => {
    expect(burndown([day("2026-11-01", 1, 150)], "2026-11-01", 100).budgetUsed).toBeCloseTo(1.5);
  });
});
