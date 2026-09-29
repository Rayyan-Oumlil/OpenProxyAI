import type { Scene } from '../types';

export const agents: Scene = {
  id: 'agents',
  title: 'Governing agent tool calls',
  description: 'Agents reach MCP tool servers only through the gateway, which checks each agent identity against its tool policy.',
  viewBox: { w: 1000, h: 560 },
  nodes: [
    { id: 'agent-support', kind: 'agent', label: 'support-agent', x: 120, y: 140 },
    { id: 'agent-coder', kind: 'agent', label: 'coding-agent', x: 120, y: 280 },
    { id: 'agent-ops', kind: 'agent', label: 'ops-agent', x: 120, y: 420 },
    { id: 'gw', kind: 'gateway', label: 'MCP gateway', x: 480, y: 280 },
    { id: 'mcp-github', kind: 'tool', label: 'MCP · github', x: 860, y: 110 },
    { id: 'mcp-jira', kind: 'tool', label: 'MCP · jira', x: 860, y: 230 },
    { id: 'mcp-db', kind: 'tool', label: 'MCP · postgres', x: 860, y: 350 },
    { id: 'claude', kind: 'model', label: 'claude', x: 860, y: 470 },
  ],
  edges: [
    { from: 'agent-support', to: 'gw' }, { from: 'agent-coder', to: 'gw' }, { from: 'agent-ops', to: 'gw' },
    { from: 'gw', to: 'mcp-github' }, { from: 'gw', to: 'mcp-jira' }, { from: 'gw', to: 'mcp-db' }, { from: 'gw', to: 'claude' },
  ],
  flows: [
    { id: 'support-jira', path: ['agent-support', 'gw', 'mcp-jira'], weights: { ok: 5, redacted: 2 } },
    { id: 'support-db', path: ['agent-support', 'gw', 'mcp-db'], weights: { blocked_446: 1 } },
    { id: 'coder-github', path: ['agent-coder', 'gw', 'mcp-github'], weights: { ok: 6, rate_429: 1 } },
    { id: 'coder-claude', path: ['agent-coder', 'gw', 'claude'], weights: { ok: 4, cache_hit: 2, budget_402: 1 } },
    { id: 'ops-db', path: ['agent-ops', 'gw', 'mcp-db'], weights: { ok: 3, blocked_446: 1 } },
  ],
};
