import type { Scene } from '../types';

export const home: Scene = {
  id: 'home',
  title: 'OpenProxyAI control plane',
  description: 'Applications and agents send every model call and tool call through one gateway, which routes to model providers and MCP tools and writes an audit log.',
  viewBox: { w: 1000, h: 560 },
  nodes: [
    { id: 'app-support', kind: 'client', label: 'support-bot', x: 160, y: 110 },
    { id: 'app-finance', kind: 'client', label: 'finance-app', x: 160, y: 230 },
    { id: 'agent-research', kind: 'agent', label: 'research-agent', x: 160, y: 350 },
    { id: 'agent-ops', kind: 'agent', label: 'ops-agent', x: 160, y: 460 },
    { id: 'gw', kind: 'gateway', label: 'OpenProxyAI', x: 500, y: 280 },
    { id: 'openai', kind: 'model', label: 'OpenAI', x: 880, y: 80 },
    { id: 'anthropic', kind: 'model', label: 'Anthropic', x: 880, y: 180 },
    { id: 'azure', kind: 'model', label: 'Azure OpenAI', x: 880, y: 280 },
    { id: 'mistral', kind: 'model', label: 'Mistral', x: 880, y: 380 },
    { id: 'mcp-github', kind: 'tool', label: 'MCP · github', x: 880, y: 470 },
    { id: 'audit', kind: 'store', label: 'audit log', x: 500, y: 500 },
  ],
  edges: [
    { from: 'app-support', to: 'gw' }, { from: 'app-finance', to: 'gw' },
    { from: 'agent-research', to: 'gw' }, { from: 'agent-ops', to: 'gw' },
    { from: 'gw', to: 'openai' }, { from: 'gw', to: 'anthropic' }, { from: 'gw', to: 'azure' },
    { from: 'gw', to: 'mistral' }, { from: 'gw', to: 'mcp-github' }, { from: 'gw', to: 'audit' },
  ],
  flows: [
    { id: 'support-openai', path: ['app-support', 'gw', 'openai'], weights: { ok: 5, cache_hit: 3, redacted: 1 } },
    { id: 'finance-anthropic', path: ['app-finance', 'gw', 'anthropic'], weights: { ok: 4, redacted: 3, blocked_446: 1 } },
    { id: 'finance-azure', path: ['app-finance', 'gw', 'azure'], weights: { ok: 4, budget_402: 1 } },
    { id: 'research-mistral', path: ['agent-research', 'gw', 'mistral'], weights: { ok: 4, cache_hit: 2, rate_429: 1 } },
    { id: 'ops-github', path: ['agent-ops', 'gw', 'mcp-github'], weights: { ok: 3, blocked_446: 2 } },
  ],
};
