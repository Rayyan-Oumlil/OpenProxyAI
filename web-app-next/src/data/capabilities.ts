export type Pillar = 'models' | 'agents' | 'trust' | 'finops';
export type BacklogId = 'B1' | 'B2' | 'B3' | 'B4' | 'B5' | 'B6';

interface Base { id: string; pillar: Pillar; title: string; summary: string }
export type Capability =
  | (Base & { status: 'built'; source: string })
  | (Base & { status: 'backlog'; backlogId: BacklogId });

const S = 'backend/app/services';

export const CAPABILITIES: readonly Capability[] = [
  // Models
  { id: 'routing', pillar: 'models', status: 'built', source: `${S}/llm_service.py`, title: 'Routing strategies', summary: 'Shuffle, round-robin or lowest-latency across weighted provider keys, overridable per org.' },
  { id: 'fallback', pillar: 'models', status: 'built', source: `${S}/llm_service.py`, title: 'Provider fallback', summary: 'Retries 429s and 5xx on the next key or a fallback model. Never retries client errors.' },
  { id: 'circuit-breaker', pillar: 'models', status: 'built', source: `${S}/circuit_breaker_service.py`, title: 'Circuit breaker', summary: 'A key that keeps failing is skipped until its cooldown ends, so one outage never cascades.' },
  { id: 'adaptive-lb', pillar: 'models', status: 'built', source: `${S}/adaptive_sampling_service.py`, title: 'Adaptive load balancing', summary: 'Effective weights shift toward keys with lower latency and error rates.' },
  { id: 'cache', pillar: 'models', status: 'built', source: `${S}/cache_service.py`, title: 'Three-tier cache', summary: 'In-memory, Redis exact-match, then pgvector semantic match at a 0.95 similarity threshold.' },
  { id: 'residency', pillar: 'models', status: 'built', source: `${S}/llm_service.py`, title: 'Data residency', summary: 'EU organisations only route through EU or global keys, enforced in SQL.' },
  // Agents
  { id: 'mcp-gateway', pillar: 'agents', status: 'backlog', backlogId: 'B1', title: 'MCP gateway', summary: 'One endpoint in front of every MCP tool server, with per-caller tool filtering.' },
  { id: 'agent-identity', pillar: 'agents', status: 'backlog', backlogId: 'B3', title: 'Per-agent identity', summary: 'Every agent gets its own key, policies and budget, so actions are attributable.' },
  { id: 'tool-guardrails', pillar: 'agents', status: 'backlog', backlogId: 'B4', title: 'Guardrails on tool calls', summary: 'Tool arguments and results pass the same policy engine as prompts.' },
  { id: 'a2a-audit', pillar: 'agents', status: 'backlog', backlogId: 'B5', title: 'Agent-to-agent audit', summary: 'Calls between agents are logged with caller identity and cost.' },
  // Trust
  { id: 'pii', pillar: 'trust', status: 'built', source: `${S}/policy_service.py`, title: 'PII redaction', summary: 'Emails, SSNs and card numbers are redacted in prompts and in responses, streaming included.' },
  { id: 'injection', pillar: 'trust', status: 'built', source: `${S}/prompt_injection_service.py`, title: 'Prompt-injection detection', summary: 'A DeBERTa classifier scores every prompt, with pattern matching when the model is unavailable.' },
  { id: 'rls', pillar: 'trust', status: 'built', source: 'backend/alembic/versions/f8a9b0c1d2e3_add_rls_policies.py', title: 'Tenant isolation in the database', summary: 'PostgreSQL row-level security scopes every query to one organisation.' },
  { id: 'append-only-audit', pillar: 'trust', status: 'built', source: 'backend/alembic/versions/f1a9c3e7d5b2_audit_log_immutability.py', title: 'Append-only audit log', summary: 'Request logs can be written but never updated or deleted by the application role.' },
  { id: 'compliance-templates', pillar: 'trust', status: 'built', source: `${S}/compliance_templates.py`, title: 'Compliance templates', summary: 'HIPAA, PCI-DSS and FedRAMP policy presets that merge into existing org config.' },
  { id: 'sso', pillar: 'trust', status: 'built', source: `${S}/sso_service.py`, title: 'OIDC single sign-on', summary: 'Per-organisation OIDC with just-in-time user provisioning.' },
  { id: 'hash-chain', pillar: 'trust', status: 'backlog', backlogId: 'B2', title: 'Tamper-evident audit chain', summary: 'Each log entry carries the hash of the one before it, so any edit is detectable.' },
  // FinOps
  { id: 'budgets', pillar: 'finops', status: 'built', source: `${S}/rate_limiter.py`, title: 'Budgets and limits', summary: 'Requests, tokens and dollars per minute or day, per org, team and user. Over budget returns 402.' },
  { id: 'anomaly', pillar: 'finops', status: 'built', source: `${S}/cost_tracker.py`, title: 'Cost anomaly detection', summary: 'Spend is compared with a 7-day baseline per org and per user.' },
  { id: 'projection', pillar: 'finops', status: 'built', source: `${S}/analytics_service.py`, title: 'Month-end projection', summary: 'Projected spend from the daily average, next to cost by model, user and team.' },
  { id: 'chargeback', pillar: 'finops', status: 'built', source: `${S}/llm_service.py`, title: 'Chargeback labels', summary: 'Tag requests by department or project and split the bill accordingly.' },
  { id: 'spend-reports', pillar: 'finops', status: 'built', source: `${S}/spend_report_service.py`, title: 'Spend reports', summary: 'Weekly and monthly digests to Slack or email.' },
  { id: 'predictive-budgets', pillar: 'finops', status: 'backlog', backlogId: 'B6', title: 'Predictive budgets', summary: 'Forecasts the day each team will exhaust its budget.' },
];

export function capabilitiesFor(pillar: Pillar): Capability[] {
  return CAPABILITIES.filter(c => c.pillar === pillar);
}
