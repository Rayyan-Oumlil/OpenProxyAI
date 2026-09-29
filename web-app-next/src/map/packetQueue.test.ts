import { describe, expect, it } from 'vitest';
import { MAX_PACKETS, enqueuePacket } from './packetQueue';

describe('enqueuePacket', () => {
  it('appends without mutating the input', () => {
    const q = [1, 2];
    const r = enqueuePacket(q, 3);
    expect(r.queue).toEqual([1, 2, 3]);
    expect(r.evicted).toEqual([]);
    expect(q).toEqual([1, 2]);
  });

  it('never exceeds the cap, evicting the oldest', () => {
    let q: number[] = [];
    const evicted: number[] = [];
    for (let i = 0; i < 10_000; i++) {
      const r = enqueuePacket(q, i);
      q = r.queue;
      evicted.push(...r.evicted);
    }
    expect(q).toHaveLength(MAX_PACKETS);
    expect(q[0]).toBe(10_000 - MAX_PACKETS);
    expect(evicted).toHaveLength(10_000 - MAX_PACKETS);
  });
});
