import type { Outcome, RequestEvent, Scene } from '../types';
import { STATUS_CODE, headersFor, stagesFor } from './outcomes';
import { createRng, pickWeighted } from './rng';

export const EVENT_INTERVAL_MS = 700;

const FORWARDED: ReadonlySet<Outcome> = new Set(['ok', 'redacted']);

function travelledPath(scene: Scene, path: string[], outcome: Outcome): string[] {
  if (FORWARDED.has(outcome)) return path;
  const gw = path.findIndex(id => scene.nodes.find(n => n.id === id)?.kind === 'gateway');
  if (gw === -1) throw new Error(`flow path has no gateway node: ${path.join(' > ')}`);
  return path.slice(0, gw + 1);
}

export function createEngine(scene: Scene, seed: number): { next(): RequestEvent } {
  if (scene.flows.length === 0) throw new Error(`scene "${scene.id}" has no flows`);
  const rng = createRng(seed);
  let n = 0;
  return {
    next() {
      const flow = scene.flows[Math.floor(rng() * scene.flows.length)];
      const outcome = pickWeighted(rng, flow.weights);
      const id = `req_${seed.toString(36)}${n.toString(36).padStart(5, '0')}`;
      const event: RequestEvent = {
        id,
        flowId: flow.id,
        path: travelledPath(scene, flow.path, outcome),
        outcome,
        statusCode: STATUS_CODE[outcome],
        stages: stagesFor(outcome),
        headers: headersFor(outcome, id),
        atMs: n * EVENT_INTERVAL_MS,
      };
      n += 1;
      return event;
    },
  };
}

export function generate(scene: Scene, seed: number, count: number): RequestEvent[] {
  const engine = createEngine(scene, seed);
  return Array.from({ length: count }, () => engine.next());
}
