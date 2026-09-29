import { useId, useState } from 'react';

export interface CodeTab { label: string; code: string }

export default function CodeTabs({ tabs }: { tabs: CodeTab[] }) {
  const [active, setActive] = useState(0);
  const base = useId();
  if (tabs.length === 0) throw new Error('CodeTabs: at least one tab is required');
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <div role="tablist" aria-label="Code samples" className="flex border-b border-line">
        {tabs.map((t, i) => (
          <button
            key={t.label}
            role="tab"
            id={`${base}-tab-${i}`}
            aria-selected={i === active}
            aria-controls={`${base}-panel-${i}`}
            onClick={() => setActive(i)}
            className={`px-4 py-2 font-mono text-step--1 ${i === active ? 'text-ink border-b-2 border-signal' : 'text-ink-dim'}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tabs.map((t, i) => (
        <pre
          key={t.label}
          role="tabpanel"
          id={`${base}-panel-${i}`}
          aria-labelledby={`${base}-tab-${i}`}
          hidden={i !== active}
          className="overflow-x-auto p-5 font-mono text-step--1 leading-relaxed text-ink"
        >
          <code>{t.code}</code>
        </pre>
      ))}
    </div>
  );
}
