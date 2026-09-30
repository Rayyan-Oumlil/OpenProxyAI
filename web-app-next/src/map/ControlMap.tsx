import { useId, useRef } from 'react';
import SimulatedTag from '../components/SimulatedTag';
import { labelLayout } from './layout';
import type { NodeKind, RequestEvent, Scene } from './types';
import { useMapAnimation } from './useMapAnimation';

interface ControlMapProps {
  scene: Scene;
  seed?: number;
  animate?: boolean;
  onEvent?: (e: RequestEvent) => void;
  className?: string;
}

const NODE_STYLE: Record<NodeKind, { r: number; fill: string; stroke: string }> = {
  client: { r: 7, fill: 'var(--surface-2)', stroke: 'var(--ink-dim)' },
  agent: { r: 7, fill: 'var(--surface-2)', stroke: 'var(--ok)' },
  gateway: { r: 22, fill: 'var(--surface)', stroke: 'var(--signal)' },
  model: { r: 7, fill: 'var(--surface-2)', stroke: 'var(--ink)' },
  tool: { r: 7, fill: 'var(--surface-2)', stroke: 'var(--ok)' },
  store: { r: 7, fill: 'var(--surface-2)', stroke: 'var(--ink-dim)' },
};

// On phones the SVG is ~0.36x scale, so labels would render at ~5px; a legend replaces them there.
const LEGEND_GROUPS: { title: string; kinds: NodeKind[] }[] = [
  { title: 'From', kinds: ['client', 'agent'] },
  { title: 'Through', kinds: ['gateway'] },
  { title: 'To', kinds: ['model', 'tool', 'store'] },
];

export default function ControlMap({ scene, seed = 7, animate = true, onEvent, className }: ControlMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const titleId = useId();
  const descId = useId();
  const byId = new Map(scene.nodes.map(n => [n.id, n]));
  useMapAnimation(svgRef, scene, seed, animate, onEvent);

  return (
    <figure className={`relative ${className ?? ''}`}>
      <div className="absolute right-3 top-3 z-10"><SimulatedTag /></div>
      <svg
        ref={svgRef}
        role="img"
        aria-labelledby={titleId}
        aria-describedby={descId}
        viewBox={`0 0 ${scene.viewBox.w} ${scene.viewBox.h}`}
        className="h-auto w-full"
      >
        <title id={titleId}>{scene.title}</title>
        <desc id={descId}>{scene.description}</desc>
        <g fill="none" stroke="var(--line)" strokeWidth={1.5}>
          {scene.edges.map(e => {
            const a = byId.get(e.from);
            const b = byId.get(e.to);
            if (!a || !b) throw new Error(`ControlMap: edge ${e.from}>${e.to} references a missing node`);
            return (
              <path
                key={`${e.from}>${e.to}`}
                id={`edge-${scene.id}-${e.from}-${e.to}`}
                data-edge={`${e.from}>${e.to}`}
                d={`M ${a.x} ${a.y} C ${(a.x + b.x) / 2} ${a.y}, ${(a.x + b.x) / 2} ${b.y}, ${b.x} ${b.y}`}
              />
            );
          })}
        </g>
        <g data-layer="packets" />
        <g>
          {scene.nodes.map(n => {
            const s = NODE_STYLE[n.kind];
            const l = labelLayout(n, scene.viewBox.w);
            return (
              <g key={n.id} data-node={n.id}>
                <circle cx={n.x} cy={n.y} r={s.r} fill={s.fill} stroke={s.stroke} strokeWidth={n.kind === 'gateway' ? 2 : 1.5} />
                <text
                  x={l.x}
                  y={n.kind === 'gateway' ? n.y + 44 : n.y + 4}
                  textAnchor={l.anchor}
                  className="fill-ink-dim font-mono max-sm:hidden"
                  fontSize={l.fontSize}
                >
                  {n.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      <ul aria-label="Map legend" className="mt-3 grid grid-cols-3 gap-3 px-2 pb-2 font-mono text-[11px] text-ink-dim sm:hidden">
        {LEGEND_GROUPS.map(group => (
          <li key={group.title}>
            <span className="text-ink">{group.title}</span>
            <ul className="mt-1 space-y-0.5">
              {scene.nodes.filter(n => group.kinds.includes(n.kind)).map(n => <li key={n.id}>{n.label}</li>)}
            </ul>
          </li>
        ))}
      </ul>
      <figcaption className="sr-only">
        {scene.description} Nodes: {scene.nodes.map(n => n.label).join(', ')}.
      </figcaption>
    </figure>
  );
}
