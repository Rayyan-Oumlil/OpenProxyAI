import type { Scene } from '../types';

export const models: Scene = {
  id: 'models',
  title: 'Routing across model providers',
  description: 'The gateway spreads traffic across weighted provider keys; a key that keeps failing is skipped by the circuit breaker.',
  viewBox: { w: 1000, h: 560 },
  nodes: [
    { id: 'apps', kind: 'client', label: 'your apps', x: 120, y: 280 },
    { id: 'gw', kind: 'gateway', label: 'router', x: 440, y: 280 },
    { id: 'openai-1', kind: 'model', label: 'openai · key 1', x: 860, y: 90 },
    { id: 'openai-2', kind: 'model', label: 'openai · key 2', x: 860, y: 200 },
    { id: 'anthropic', kind: 'model', label: 'anthropic', x: 860, y: 310 },
    { id: 'azure-eu', kind: 'model', label: 'azure · eu', x: 860, y: 420 },
    { id: 'cache', kind: 'store', label: 'L1 · L2 · L3 cache', x: 440, y: 480 },
  ],
  edges: [
    { from: 'apps', to: 'gw' },
    { from: 'gw', to: 'openai-1' }, { from: 'gw', to: 'openai-2' }, { from: 'gw', to: 'anthropic' },
    { from: 'gw', to: 'azure-eu' }, { from: 'gw', to: 'cache' },
  ],
  flows: [
    { id: 'o1', path: ['apps', 'gw', 'openai-1'], weights: { ok: 5, rate_429: 2 } },
    { id: 'o2', path: ['apps', 'gw', 'openai-2'], weights: { ok: 6, cache_hit: 3 } },
    { id: 'an', path: ['apps', 'gw', 'anthropic'], weights: { ok: 5, cache_hit: 2 } },
    { id: 'eu', path: ['apps', 'gw', 'azure-eu'], weights: { ok: 4, budget_402: 1 } },
  ],
};
