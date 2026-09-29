// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { GENESIS, SAMPLE_ENTRIES, buildChain, canonicalJson, sha256Hex, verifyChain } from './chain';

describe('audit chain', () => {
  it('hashes with SHA-256', async () => {
    expect(await sha256Hex('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  });

  it('canonical JSON is key-order independent', () => {
    const a = { seq: 1, actor: 'x', action: 'y', model: 'm', status: 200 };
    const b = { status: 200, model: 'm', action: 'y', actor: 'x', seq: 1 };
    expect(canonicalJson(a)).toBe(canonicalJson(b));
  });

  it('links each entry to the previous hash', async () => {
    const links = await buildChain(SAMPLE_ENTRIES);
    expect(links[0].prevHash).toBe(GENESIS);
    links.slice(1).forEach((l, i) => expect(l.prevHash).toBe(links[i].hash));
  });

  it('verifies an untouched chain', async () => {
    expect(await verifyChain(await buildChain(SAMPLE_ENTRIES))).toEqual(SAMPLE_ENTRIES.map(() => true));
  });

  it('an edit invalidates exactly that link and everything after it', async () => {
    const links = await buildChain(SAMPLE_ENTRIES);
    const tampered = links.map((l, i) => (i === 2 ? { ...l, entry: { ...l.entry, action: 'export_all_logs' } } : l));
    expect(await verifyChain(tampered)).toEqual(SAMPLE_ENTRIES.map((_, i) => i < 2));
  });
});
