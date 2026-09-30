import type { Capability } from '../data/capabilities';
import { sourceUrl } from '../site/links';

export default function FeatureGrid({ items }: { items: Capability[] }) {
  return (
    <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {items.map(c => (
        <li key={c.id} className="flex flex-col rounded-xl border border-line bg-surface p-5">
          <h3 className="text-step-1 font-semibold">{c.title}</h3>
          <p className="mt-2 flex-1 text-ink-dim">{c.summary}</p>
          {c.status === 'built' && (
            <a href={sourceUrl(c.source)} className="mt-4 font-mono text-step--1 text-ok hover:underline">
              view source ↗
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}
