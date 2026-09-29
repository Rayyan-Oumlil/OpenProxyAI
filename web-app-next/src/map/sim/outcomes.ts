import type { Outcome, StageName, StageResult } from '../types';

export const STAGES: readonly StageName[] = ['auth', 'rate_limit', 'policy', 'cache', 'route', 'upstream', 'log'];

export const STATUS_CODE: Record<Outcome, number> = {
  ok: 200, cache_hit: 200, redacted: 200, blocked_446: 446, budget_402: 402, rate_429: 429,
};

const FAIL_AT: Partial<Record<Outcome, StageName>> = {
  blocked_446: 'policy', budget_402: 'rate_limit', rate_429: 'rate_limit',
};

const DEFAULT_DETAIL: Record<StageName, string> = {
  auth: 'api key verified · sha-256',
  rate_limit: 'within rpm · tpm · $/day',
  policy: 'allow',
  cache: 'L1 miss · L2 miss · L3 miss',
  route: 'weighted key selected',
  upstream: 'litellm.acompletion',
  log: 'async · fire-and-forget',
};

const OVERRIDES: Record<Outcome, Partial<Record<StageName, string>>> = {
  ok: {},
  cache_hit: { cache: 'L3 semantic hit · sim 0.97' },
  redacted: { policy: 'pii_redact · 1 span' },
  blocked_446: { policy: 'blocked keyword · guardrail' },
  budget_402: { rate_limit: 'daily budget exceeded' },
  rate_429: { rate_limit: 'requests/min limit' },
};

export function stagesFor(outcome: Outcome): StageResult[] {
  const failAt = FAIL_AT[outcome];
  let stopped = false;
  return STAGES.map((stage): StageResult => {
    if (stage === 'log') return { stage, status: 'pass', detail: DEFAULT_DETAIL.log };
    if (stopped) return { stage, status: 'skip', detail: '—' };
    const detail = OVERRIDES[outcome][stage] ?? DEFAULT_DETAIL[stage];
    if (stage === failAt) {
      stopped = true;
      return { stage, status: 'fail', detail };
    }
    if (outcome === 'cache_hit' && (stage === 'route' || stage === 'upstream')) {
      return { stage, status: 'skip', detail: 'served from cache' };
    }
    return { stage, status: 'pass', detail };
  });
}

export function headersFor(outcome: Outcome, id: string): Record<string, string> {
  const headers: Record<string, string> = { 'X-OpenProxyAI-Request-Id': id };
  const reachedPolicy = outcome !== 'budget_402' && outcome !== 'rate_429';
  if (reachedPolicy) {
    headers['X-OpenProxyAI-Policy-Action'] = outcome === 'blocked_446' ? 'block' : outcome === 'redacted' ? 'redact' : 'allow';
  }
  if (reachedPolicy && outcome !== 'blocked_446') {
    headers['X-OpenProxyAI-Cache'] = outcome === 'cache_hit' ? 'HIT' : 'MISS';
  }
  return headers;
}
