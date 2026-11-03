import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const PLACEHOLDER = "\u2014"; // em dash: a value we cannot show

const INTEGER = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const COMPACT = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const MONEY = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const MONEY_WHOLE = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 });

/** Exact counts with thousands separators; only millions and up are abbreviated (12,345 stays 12,345). */
export function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return PLACEHOLDER;
  return Math.abs(n) >= 1_000_000 ? COMPACT.format(n) : INTEGER.format(n);
}

/** Short form for chart axes, where space is tight: 1.2K, 3M. */
export function formatCompact(n: number): string {
  return Number.isFinite(n) ? COMPACT.format(n) : PLACEHOLDER;
}

/**
 * Spend as money. Whole-cent precision from $1 up, and enough digits below that for a single
 * request's cost to stay visible ($0.0042, $0.000031) instead of rounding to $0.00.
 */
export function formatCost(usd: number): string {
  if (!Number.isFinite(usd)) return PLACEHOLDER;
  if (usd === 0) return MONEY.format(0);
  const abs = Math.abs(usd);
  if (abs >= 1) return MONEY.format(usd);
  if (abs >= 0.001) return `${usd < 0 ? "-" : ""}$${abs.toFixed(4)}`;
  return `${usd < 0 ? "-" : ""}$${abs.toFixed(6)}`;
}

/** Money on a chart axis: $0.0035, $12, $2.5K. No trailing zeros, never $2000.000. */
export function formatAxisCost(usd: number): string {
  if (!Number.isFinite(usd)) return PLACEHOLDER;
  const abs = Math.abs(usd);
  const sign = usd < 0 ? "-" : "";
  if (abs >= 1000) return `${sign}$${COMPACT.format(abs)}`;
  if (abs >= 1) return MONEY_WHOLE.format(usd);
  if (abs === 0) return "$0";
  return `${sign}$${Number(abs.toPrecision(2)).toString()}`;
}

/** A ratio (0 to 1) as a percentage with one decimal: 0.982 becomes 98.2%. */
export function formatPercent(ratio: number, digits = 1): string {
  return Number.isFinite(ratio) ? `${(ratio * 100).toFixed(digits)}%` : PLACEHOLDER;
}

export function formatLatency(ms: number): string {
  if (!Number.isFinite(ms)) return PLACEHOLDER;
  if (ms >= 60_000) {
    const minutes = Math.floor(ms / 60_000);
    const seconds = Math.round((ms % 60_000) / 1000);
    return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
  }
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

/** Parse an ISO timestamp from the backend (which may lack timezone info) as UTC. */
function parseUTC(iso: string): Date {
  // Backend sends naive datetimes (no Z / +00:00). Without a timezone suffix,
  // JS treats the string as local time, showing UTC values 4h late for UTC-4 users.
  // Appending Z forces UTC interpretation so toLocaleString() converts correctly.
  if (!iso.endsWith("Z") && !iso.includes("+")) return new Date(iso + "Z");
  return new Date(iso);
}

export function formatDate(iso: string): string {
  return parseUTC(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateShort(iso: string): string {
  return parseUTC(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  return parseUTC(iso).toLocaleString();
}
