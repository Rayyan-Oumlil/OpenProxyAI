import { useEffect, useRef, type RefObject } from 'react';
import { createEngine, EVENT_INTERVAL_MS } from './sim/engine';
import { enqueuePacket } from './packetQueue';
import type { Outcome, RequestEvent, Scene } from './types';

const SVG_NS = 'http://www.w3.org/2000/svg';
const SEGMENT_SECONDS = 0.9;

const COLOR: Record<Outcome, string> = {
  ok: 'var(--ink)', cache_hit: 'var(--ok)', redacted: 'var(--signal)',
  blocked_446: 'var(--danger)', budget_402: 'var(--danger)', rate_429: 'var(--signal)',
};

interface Live { el: SVGCircleElement; kill: () => void }

export function useMapAnimation(
  svgRef: RefObject<SVGSVGElement | null>,
  scene: Scene,
  seed: number,
  enabled: boolean,
  onEvent?: (e: RequestEvent) => void,
): void {
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!enabled || !svg) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const layer = svg.querySelector<SVGGElement>('[data-layer="packets"]');
    if (!layer) throw new Error('useMapAnimation: packet layer missing from ControlMap');

    let cancelled = false;
    let visible = true;
    let live: Live[] = [];
    let timer: ReturnType<typeof setInterval> | undefined;
    const observer = typeof IntersectionObserver === 'undefined'
      ? null
      : new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
    observer?.observe(svg);

    const remove = (el: SVGCircleElement) => {
      live = live.filter(p => p.el !== el);
      el.remove();
    };

    (async () => {
      const [{ gsap }, { MotionPathPlugin }] = await Promise.all([import('gsap'), import('gsap/MotionPathPlugin')]);
      if (cancelled) return;
      gsap.registerPlugin(MotionPathPlugin);
      const engine = createEngine(scene, seed);

      const spawn = () => {
        if (!visible || document.hidden) return;
        const event = engine.next();
        onEventRef.current?.(event);

        const el = document.createElementNS(SVG_NS, 'circle');
        el.setAttribute('r', '4');
        el.setAttribute('fill', COLOR[event.outcome]);
        layer.appendChild(el);

        const tl = gsap.timeline({ onComplete: () => remove(el) });
        event.path.slice(1).forEach((to, i) => {
          const edge = svg.querySelector<SVGPathElement>(`#edge-${scene.id}-${event.path[i]}-${to}`);
          if (!edge) throw new Error(`useMapAnimation: no edge ${event.path[i]}>${to} in scene ${scene.id}`);
          tl.to(el, { duration: SEGMENT_SECONDS, ease: 'none', motionPath: { path: edge, align: edge, alignOrigin: [0.5, 0.5] } });
        });
        if (event.statusCode >= 400) tl.to(el, { duration: 0.35, attr: { r: 10 }, opacity: 0 });
        else tl.to(el, { duration: 0.25, opacity: 0 });

        const { queue, evicted } = enqueuePacket(live, { el, kill: () => tl.kill() });
        live = queue;
        evicted.forEach(p => { p.kill(); p.el.remove(); });
      };

      spawn();
      timer = setInterval(spawn, EVENT_INTERVAL_MS);
    })();

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      observer?.disconnect();
      live.forEach(p => { p.kill(); p.el.remove(); });
      live = [];
    };
  }, [svgRef, scene, seed, enabled]);
}
