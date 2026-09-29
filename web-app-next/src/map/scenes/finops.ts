import type { Scene } from '../types';

export const finops: Scene = {
  id: 'finops',
  title: 'Spend by team',
  description: 'Each team spends against its own budget; requests over budget are stopped with HTTP 402 before any tokens are bought.',
  viewBox: { w: 1000, h: 560 },
  nodes: [
    { id: 'team-eng', kind: 'client', label: 'engineering', x: 120, y: 120 },
    { id: 'team-support', kind: 'client', label: 'support', x: 120, y: 280 },
    { id: 'team-research', kind: 'client', label: 'research', x: 120, y: 440 },
    { id: 'gw', kind: 'gateway', label: 'budget ledger', x: 480, y: 280 },
    { id: 'gpt', kind: 'model', label: 'gpt · $', x: 860, y: 180 },
    { id: 'claude', kind: 'model', label: 'claude · $', x: 860, y: 380 },
  ],
  edges: [
    { from: 'team-eng', to: 'gw' }, { from: 'team-support', to: 'gw' }, { from: 'team-research', to: 'gw' },
    { from: 'gw', to: 'gpt' }, { from: 'gw', to: 'claude' },
  ],
  flows: [
    { id: 'eng', path: ['team-eng', 'gw', 'gpt'], weights: { ok: 5, cache_hit: 2 } },
    { id: 'support', path: ['team-support', 'gw', 'claude'], weights: { ok: 4, cache_hit: 3 } },
    { id: 'research', path: ['team-research', 'gw', 'claude'], weights: { ok: 3, budget_402: 2 } },
  ],
};
