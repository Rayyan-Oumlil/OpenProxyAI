export interface Decision { title: string; choice: string; tradeoff: string; source: string }

export const DECISIONS: readonly Decision[] = [
  {
    title: 'LiteLLM as a library, not a proxy',
    choice: 'Call litellm.acompletion() inside our own FastAPI pipeline instead of running LiteLLM’s proxy server.',
    tradeoff: 'We own auth, policy, caching and logging end to end, at the cost of re-implementing features their proxy ships with.',
    source: 'backend/app/services/llm_service.py',
  },
  {
    title: 'Logging never blocks the response',
    choice: 'Audit logging runs as a fire-and-forget background task that opens its own database session.',
    tradeoff: 'Responses stay fast, but a crash between response and write can lose a log line — which is why the write path is kept small.',
    source: 'backend/app/services/audit_logger.py',
  },
  {
    title: 'Tenant isolation in the database',
    choice: 'PostgreSQL row-level security keyed on a transaction-scoped app.current_org_id setting.',
    tradeoff: 'A missed filter in application code cannot leak another tenant’s rows, but every session must set the org first or it sees nothing.',
    source: 'backend/app/database.py',
  },
  {
    title: 'Guardrails as hooks',
    choice: 'Policies run as before_request / after_request hooks with off, log_only and enforce modes per organisation.',
    tradeoff: 'New guardrails plug in without touching the proxy route; ordering between hooks has to be managed explicitly.',
    source: 'backend/app/services/policy_service.py',
  },
  {
    title: 'Status codes that say why',
    choice: '446 for a guardrail block, 402 for an exhausted budget, 429 for a rate limit.',
    tradeoff: 'Clients can branch on the cause without parsing bodies; 446 is non-standard and has to be documented.',
    source: 'backend/app/routes/proxy.py',
  },
  {
    title: 'A stateless MCP gateway',
    choice: 'Each upstream tool call runs its own MCP initialize handshake instead of the gateway holding long-lived sessions.',
    tradeoff: 'Nothing to store or rebalance when the gateway scales out, at the cost of one extra round-trip per tool call.',
    source: 'backend/app/services/mcp_client.py',
  },
  {
    title: 'Three cache tiers',
    choice: 'In-process TTL cache, then Redis exact match, then pgvector semantic similarity at 0.95.',
    tradeoff: 'Cheap hits stay cheap, but semantic hits can return a near-miss answer — so the threshold is strict and overridable per request.',
    source: 'backend/app/services/cache_service.py',
  },
];
