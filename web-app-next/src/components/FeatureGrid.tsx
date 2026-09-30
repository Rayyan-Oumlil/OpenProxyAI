import type { Capability } from '../data/capabilities';
import { sourceUrl } from '../site/links';

export default function FeatureGrid({ items }: { items: Capability[] }) {
  return (
    <ul className="grid gap-x-12 md:grid-cols-2">
      {items.map(c => (
        <li key={c.id} className="min-w-0 border-t border-line py-6">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="text-step-1 font-semibold">{c.title}</h3>
            {c.status === 'built' && (
              <a href={sourceUrl(c.source)} className="shrink-0 font-mono text-step--1 text-ok hover:underline">
                view source
              </a>
            )}
          </div>
          <p className="mt-2 max-w-prose text-ink-dim">{c.summary}</p>
        </li>
      ))}
    </ul>
  );
}
