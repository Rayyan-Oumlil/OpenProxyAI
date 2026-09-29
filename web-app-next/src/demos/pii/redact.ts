// Ported verbatim from backend/app/services/policy_service.py (PolicyService._EMAIL_RE, _SSN_RE, _CC_RE),
// applied in the same order with the same replacement token.
export const MAX_INPUT = 2000;
export const REDACTED = '[REDACTED]';

const PATTERNS = [
  ['email', /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g],
  ['ssn', /\b\d{3}-\d{2}-\d{4}\b/g],
  ['credit_card', /\b(?:\d[ -]*?){13,19}\b/g],
] as const;

export type PiiKind = (typeof PATTERNS)[number][0];

export function redact(text: string): { output: string; hits: Record<PiiKind, number> } {
  const hits: Record<PiiKind, number> = { email: 0, ssn: 0, credit_card: 0 };
  const output = PATTERNS.reduce((acc, [kind, re]) => acc.replace(re, () => {
    hits[kind] += 1;
    return REDACTED;
  }), text);
  return { output, hits };
}
