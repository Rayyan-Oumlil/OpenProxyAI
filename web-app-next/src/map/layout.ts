import type { MapNode } from './types';

// JetBrains Mono advances 0.6em per glyph; labels render at 13px (16px for the gateway).
const CHAR_WIDTH_EM = 0.6;
export const LABEL_FONT_SIZE = 13;
export const GATEWAY_LABEL_FONT_SIZE = 16;
const LABEL_GAP = 14;

export interface LabelLayout { x: number; anchor: 'start' | 'middle' | 'end'; fontSize: number }

export function labelLayout(n: MapNode, viewBoxWidth: number): LabelLayout {
  if (n.kind === 'gateway') return { x: n.x, anchor: 'middle', fontSize: GATEWAY_LABEL_FONT_SIZE };
  return n.x < viewBoxWidth / 2
    ? { x: n.x - LABEL_GAP, anchor: 'end', fontSize: LABEL_FONT_SIZE }
    : { x: n.x + LABEL_GAP, anchor: 'start', fontSize: LABEL_FONT_SIZE };
}

export function labelExtent(n: MapNode, viewBoxWidth: number): { left: number; right: number } {
  const { x, anchor, fontSize } = labelLayout(n, viewBoxWidth);
  const width = n.label.length * fontSize * CHAR_WIDTH_EM;
  if (anchor === 'end') return { left: x - width, right: x };
  if (anchor === 'start') return { left: x, right: x + width };
  return { left: x - width / 2, right: x + width / 2 };
}
