import { describe, expect, it } from 'vitest';
import { generate } from '../sim/engine';
import { SCENES } from './index';

const OUTCOMES = new Set(['ok', 'cache_hit', 'redacted', 'blocked_446', 'budget_402', 'rate_429']);

describe.each(Object.values(SCENES))('scene $id', scene => {
  const ids = new Set(scene.nodes.map(n => n.id));
  const edgeKeys = new Set(scene.edges.map(e => `${e.from}>${e.to}`));

  it('has unique node ids', () => {
    expect(ids.size).toBe(scene.nodes.length);
  });
  it('keeps nodes inside the viewBox with a 40px margin', () => {
    for (const n of scene.nodes) {
      expect(n.x).toBeGreaterThanOrEqual(40); expect(n.x).toBeLessThanOrEqual(scene.viewBox.w - 40);
      expect(n.y).toBeGreaterThanOrEqual(40); expect(n.y).toBeLessThanOrEqual(scene.viewBox.h - 40);
    }
  });
  it('only connects existing nodes', () => {
    for (const e of scene.edges) { expect(ids.has(e.from)).toBe(true); expect(ids.has(e.to)).toBe(true); }
  });
  it('routes every flow along existing edges through exactly one gateway', () => {
    for (const f of scene.flows) {
      f.path.slice(1).forEach((to, i) => expect(edgeKeys.has(`${f.path[i]}>${to}`)).toBe(true));
      const gateways = f.path.filter(id => scene.nodes.find(n => n.id === id)?.kind === 'gateway');
      expect(gateways).toHaveLength(1);
      Object.keys(f.weights).forEach(k => expect(OUTCOMES.has(k)).toBe(true));
    }
  });
  it('runs through the engine', () => {
    expect(generate(scene, 1, 100)).toHaveLength(100);
  });
});

it('defines one scene per page', () => {
  expect(Object.keys(SCENES).sort()).toEqual(['agents', 'finops', 'home', 'models', 'trust']);
});
