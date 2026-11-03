import type { DailyUsageTrend } from "../../api/types";

/** The backend caps `period_days` at 90, so a previous period can only be compared for windows up to 45 days. */
export const MAX_PERIOD_DAYS = 90;

export type Day = DailyUsageTrend;

export interface Totals {
  requests: number;
  tokens: number;
  cost: number;
  /** Mean latency weighted by each day's requests, so a quiet day does not count as much as a busy one. */
  avgLatencyMs: number;
}

function emptyDay(date: string): Day {
  return { date, requests: 0, tokens: 0, cost_usd: 0, avg_latency_ms: 0 };
}

/** Calendar day (UTC) `offset` days from an ISO day, as an ISO day. */
export function shiftDay(iso: string, offset: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + offset)).toISOString().slice(0, 10);
}

/** Exactly `days` consecutive days ending at `endIso`, zero-filled where the backend sent nothing. */
export function fillDays(trend: Day[], endIso: string, days: number): Day[] {
  const byDate = new Map(trend.map((d) => [d.date, d]));
  return Array.from({ length: days }, (_, i) => {
    const date = shiftDay(endIso, i - (days - 1));
    return byDate.get(date) ?? emptyDay(date);
  });
}

export function totals(days: Day[]): Totals {
  const requests = days.reduce((sum, d) => sum + d.requests, 0);
  const weighted = days.reduce((sum, d) => sum + d.avg_latency_ms * d.requests, 0);
  return {
    requests,
    tokens: days.reduce((sum, d) => sum + d.tokens, 0),
    cost: days.reduce((sum, d) => sum + d.cost_usd, 0),
    avgLatencyMs: requests > 0 ? weighted / requests : 0,
  };
}

export interface PeriodSplit {
  current: Day[];
  /** Null when the window is too long to have a comparable previous period. */
  previous: Day[] | null;
}

/**
 * Splits a trend covering `2 * days` into the current period and the one before it. Pass a trend of
 * `days` only (or a window beyond the backend cap) and `previous` is null: no delta is better than a wrong one.
 */
export function splitPeriods(trend: Day[], endIso: string, days: number, hasPrevious: boolean): PeriodSplit {
  const all = fillDays(trend, endIso, hasPrevious ? days * 2 : days);
  return hasPrevious ? { current: all.slice(days), previous: all.slice(0, days) } : { current: all, previous: null };
}

/** Whether a previous period of equal length fits inside the backend's window cap. */
export function canCompare(days: number): boolean {
  return days * 2 <= MAX_PERIOD_DAYS;
}

/** Relative change as a fraction (0.25 = +25%); null when there is nothing to compare against. */
export function change(current: number, previous: number | null | undefined): number | null {
  if (previous == null || !Number.isFinite(previous) || previous === 0) return null;
  return (current - previous) / previous;
}

export interface Burndown {
  /** Cumulative spend at the end of each day of the month so far (index 0 is day 1). */
  spent: number[];
  spentToDate: number;
  daysInMonth: number;
  /** Straight-line projection of the month's total from the average daily spend so far; null on day 0. */
  projected: number | null;
  budget: number | null;
  /** Spend as a fraction of budget; null without a budget. */
  budgetUsed: number | null;
}

/**
 * Month-to-date spend against the monthly budget. `monthTrend` must cover at least the elapsed days of
 * the month ending at `endIso`; days outside the month are ignored.
 */
export function burndown(monthTrend: Day[], endIso: string, budget: number | null): Burndown {
  const [year, month, dayOfMonth] = endIso.split("-").map(Number);
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const days = fillDays(monthTrend, endIso, dayOfMonth);
  const spent: number[] = [];
  let running = 0;
  for (const day of days) {
    running += day.cost_usd;
    spent.push(running);
  }
  const spentToDate = running;
  const validBudget = budget != null && Number.isFinite(budget) && budget > 0 ? budget : null;
  return {
    spent,
    spentToDate,
    daysInMonth,
    projected: dayOfMonth > 0 ? (spentToDate / dayOfMonth) * daysInMonth : null,
    budget: validBudget,
    budgetUsed: validBudget ? spentToDate / validBudget : null,
  };
}
