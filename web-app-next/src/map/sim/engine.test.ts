import { describe, expect, it } from 'vitest';
import type { Scene } from '../types';
import { createEngine, generate } from './engine';
import { STAGES, stagesFor } from './outcomes';
import { createRng, pickWeighted } from './rng';

const scene: Scene = {
  id: 'test', title: 't', description: 'd', viewBox: { w: 100, h: 100 },
  nodes: [
    { id: 'app', kind: 'client', label: 'App', x: 10, y: 50 },
    { id: 'gw', kind: 'gateway', label: 'Gateway', x: 50, y: 50 },
    { id: 'llm', kind: 'model', label: 'LLM', x: 90, y: 50 },
  ],
  edges: [{ from: 'app', to: 'gw' }, { from: 'gw', to: 'llm' }],
  flows: [{ id: 'f', path: ['app', 'gw', 'llm'], weights: { ok: 1, cache_hit: 1, redacted: 1, blocked_446: 1, budget_402: 1, rate_429: 1 } }],
};

describe('rng', () => {
  it('is deterministic per seed', () => {
    const a = createRng(42); const b = createRng(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });
  it('returns values in [0, 1)', () => {
    const r = createRng(1);
    for (let i = 0; i < 1000; i++) { const v = r(); expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThan(1); }
  });
  it('rejects all-zero weights', () => {
    expect(() => pickWeighted(createRng(1), { ok: 0 })).toThrow(/weights/);
  });
});

describe('engine', () => {
  it('same seed → identical event stream', () => {
    expect(generate(scene, 7, 50)).toEqual(generate(scene, 7, 50));
  });
  it('different seeds → different streams', () => {
    expect(generate(scene, 7, 50)).not.toEqual(generate(scene, 8, 50));
  });
  it('reaches every outcome', () => {
    const seen = new Set(generate(scene, 3, 500).map(e => e.outcome));
    expect([...seen].sort()).toEqual(['blocked_446', 'budget_402', 'cache_hit', 'ok', 'rate_429', 'redacted']);
  });
  it('stops packets at the gateway unless forwarded upstream', () => {
    for (const e of generate(scene, 5, 300)) {
      const forwarded = e.outcome === 'ok' || e.outcome === 'redacted';
      expect(e.path).toEqual(forwarded ? ['app', 'gw', 'llm'] : ['app', 'gw']);
    }
  });
  it('maps outcomes to real status codes', () => {
    const codes = Object.fromEntries(generate(scene, 9, 500).map(e => [e.outcome, e.statusCode]));
    expect(codes).toEqual({ ok: 200, cache_hit: 200, redacted: 200, blocked_446: 446, budget_402: 402, rate_429: 429 });
  });
  it('produces monotonic timestamps and unique ids', () => {
    const evs = generate(scene, 11, 100);
    evs.slice(1).forEach((e, i) => expect(e.atMs).toBeGreaterThan(evs[i].atMs));
    expect(new Set(evs.map(e => e.id)).size).toBe(100);
  });
  it('throws on a scene without flows', () => {
    expect(() => createEngine({ ...scene, flows: [] }, 1)).toThrow(/no flows/);
  });
  it('throws on a flow without a gateway', () => {
    const bad: Scene = { ...scene, flows: [{ id: 'x', path: ['app', 'llm'], weights: { blocked_446: 1 } }] };
    expect(() => createEngine(bad, 1).next()).toThrow(/gateway/);
  });
});

describe('stagesFor', () => {
  it('always lists the 7 stages in pipeline order', () => {
    for (const o of ['ok', 'cache_hit', 'redacted', 'blocked_446', 'budget_402', 'rate_429'] as const) {
      expect(stagesFor(o).map(s => s.stage)).toEqual([...STAGES]);
    }
  });
  it('skips everything after a failing stage except async logging', () => {
    const s = stagesFor('blocked_446');
    const failAt = s.findIndex(x => x.status === 'fail');
    expect(s[failAt].stage).toBe('policy');
    expect(s.slice(failAt + 1, -1).every(x => x.status === 'skip')).toBe(true);
    expect(s.at(-1)).toMatchObject({ stage: 'log', status: 'pass' });
  });
  it('budget and rate limits fail at the rate_limit stage', () => {
    expect(stagesFor('budget_402').find(x => x.status === 'fail')?.stage).toBe('rate_limit');
    expect(stagesFor('rate_429').find(x => x.status === 'fail')?.stage).toBe('rate_limit');
  });
  it('cache hits skip routing and upstream', () => {
    const s = stagesFor('cache_hit');
    expect(s.find(x => x.stage === 'route')?.status).toBe('skip');
    expect(s.find(x => x.stage === 'upstream')?.status).toBe('skip');
  });
});
