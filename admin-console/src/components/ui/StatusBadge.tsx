import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

/**
 * Governance outcomes, not generic success/error. Each verdict has its own colour and its own shape,
 * so the state is readable without colour and the table reads like a ledger.
 */
export type Verdict = "allowed" | "flagged" | "blocked" | "drifted" | "pending" | "neutral";

const LABELS: Record<Verdict, string> = {
  allowed: "Allowed",
  flagged: "Flagged",
  blocked: "Blocked",
  drifted: "Drifted",
  pending: "Pending",
  neutral: "None",
};

function Glyph({ verdict }: { verdict: Verdict }) {
  const common = { width: 10, height: 10, viewBox: "0 0 10 10", "aria-hidden": true, focusable: false } as const;
  switch (verdict) {
    case "allowed":
      return (
        <svg {...common}>
          <circle cx="5" cy="5" r="4" fill="currentColor" />
        </svg>
      );
    case "flagged":
      return (
        <svg {...common}>
          <circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M5 1.5a3.5 3.5 0 0 1 0 7z" fill="currentColor" />
        </svg>
      );
    case "blocked":
      return (
        <svg {...common}>
          <rect x="1.5" y="1.5" width="7" height="7" rx="1" fill="currentColor" />
        </svg>
      );
    case "drifted":
      return (
        <svg {...common}>
          <path d="M5 .8 9.2 5 5 9.2.8 5z" fill="currentColor" />
        </svg>
      );
    case "pending":
      return (
        <svg {...common}>
          <circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <path d="M2 5h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
  }
}

type StatusBadgeProps = {
  verdict: Verdict;
  children?: ReactNode;
  className?: string;
};

export function StatusBadge({ verdict, children, className }: StatusBadgeProps) {
  return (
    <span className={cn("verdict", className)} data-verdict={verdict}>
      <Glyph verdict={verdict} />
      {children ?? LABELS[verdict]}
    </span>
  );
}

/** Maps the policy action strings the API returns onto verdicts. */
export function verdictForPolicyAction(action: string | null | undefined): Verdict {
  switch (action) {
    case "allow":
      return "allowed";
    case "log_only":
    case "log":
    case "redact":
      return "flagged";
    case "block":
      return "blocked";
    default:
      return "neutral";
  }
}
