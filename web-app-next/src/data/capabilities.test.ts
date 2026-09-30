// @vitest-environment node
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { CAPABILITIES, capabilitiesFor } from './capabilities';

const REPO = resolve(__dirname, '..', '..', '..');

describe('capabilities', () => {
  it('has unique ids', () => {
    const ids = CAPABILITIES.map(c => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('every built capability points at a file that exists in the repo', () => {
    const missing = CAPABILITIES.filter(c => c.status === 'built' && !existsSync(resolve(REPO, c.source)))
      .map(c => (c.status === 'built' ? `${c.id} → ${c.source}` : c.id));
    expect(missing).toEqual([]);
  });

  it('traces every backlog item B1–B6 exactly once, whether still planned or shipped', () => {
    const ids = CAPABILITIES.flatMap(c => (c.status === 'backlog' ? [c.backlogId] : c.shippedFrom ? [c.shippedFrom] : [])).sort();
    expect(ids).toEqual(['B1', 'B2', 'B3', 'B4', 'B5', 'B6']);
  });

  it('gives every pillar at least three capabilities', () => {
    for (const p of ['models', 'agents', 'trust', 'finops'] as const) {
      expect(capabilitiesFor(p).length).toBeGreaterThanOrEqual(3);
    }
  });
});
