import type { ReactNode } from 'react';

interface ChecklistCardProps {
  title: string;
  items: { text: ReactNode; ok: boolean }[];
}

/** A short card of ticks and crosses, used in page headers instead of code. */
export default function ChecklistCard({ title, items }: ChecklistCardProps) {
  return (
    <div className="opa-card" style={{ padding: 22 }}>
      <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--ink-3)', marginBottom: 14 }}>{title}</div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map((item, i) => (
          <li key={i} style={{ display: 'flex', gap: 10, fontFamily: 'var(--sans)', fontSize: 15, lineHeight: 1.5, color: 'var(--ink)' }}>
            <span aria-hidden="true" style={{ color: item.ok ? 'var(--accent)' : 'var(--err)', fontWeight: 700 }}>{item.ok ? '✓' : '×'}</span>
            <span>{item.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
