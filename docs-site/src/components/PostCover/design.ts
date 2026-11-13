/** Deterministic cover art: the same seed always draws the same picture. */

export const VIEW_WIDTH = 400;
export const VIEW_HEIGHT = 225;

export type Variant = 'rings' | 'grid' | 'routes' | 'discs';
export type Align = 'left' | 'center';

export interface CoverDesign {
  variant: Variant;
  align: Align;
  /** Centre of the green glow, in percent of the cover. */
  glowX: number;
  glowY: number;
  random: () => number;
}

const VARIANTS: readonly Variant[] = ['rings', 'grid', 'routes', 'discs'];

/** FNV-1a, 32 bit. */
function hash(text: string): number {
  let value = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    value ^= text.charCodeAt(index);
    value = Math.imul(value, 0x01000193);
  }
  return value >>> 0;
}

/** mulberry32: a small seeded generator, enough for decoration. */
function createRandom(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let mixed = Math.imul(state ^ (state >>> 15), 1 | state);
    mixed = (mixed + Math.imul(mixed ^ (mixed >>> 7), 61 | mixed)) ^ mixed;
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

export function designFor(seed: string): CoverDesign {
  const random = createRandom(hash(seed));
  const variant = VARIANTS[Math.floor(random() * VARIANTS.length)];
  const align: Align = random() < 0.5 ? 'left' : 'center';
  // Left-aligned text keeps the glow, and the busiest art, on the right.
  const glowX = align === 'left' ? 62 + random() * 30 : 25 + random() * 50;
  const glowY = 15 + random() * 70;
  return {variant, align, glowX, glowY, random};
}

/** Rounded to 2 decimals so server and browser print identical markup. */
export function round(value: number): number {
  return Math.round(value * 100) / 100;
}
