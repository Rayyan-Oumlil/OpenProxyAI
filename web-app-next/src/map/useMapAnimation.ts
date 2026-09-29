import type { RefObject } from 'react';
import type { RequestEvent, Scene } from './types';

export function useMapAnimation(
  _svgRef: RefObject<SVGSVGElement | null>,
  _scene: Scene,
  _seed: number,
  _enabled: boolean,
  _onEvent?: (e: RequestEvent) => void,
): void {}
