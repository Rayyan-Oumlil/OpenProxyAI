import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.001) return `$${usd.toFixed(6)}`;
  if (usd < 1) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function formatLatency(ms: number): string {
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
