export const MAX_PACKETS = 24;

export function enqueuePacket<T>(queue: readonly T[], item: T, max: number = MAX_PACKETS): { queue: T[]; evicted: T[] } {
  const next = [...queue, item];
  const overflow = Math.max(0, next.length - max);
  return { queue: next.slice(overflow), evicted: next.slice(0, overflow) };
}
