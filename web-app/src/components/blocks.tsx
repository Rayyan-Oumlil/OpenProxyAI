import type { ReactNode } from 'react';

interface Item { title: ReactNode; body: ReactNode }

/** Numbered cards on a responsive grid. */
export function CardGrid({ items, min = 300 }: { items: Item[]; min?: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(min(${min}px, 100%), 1fr))`, gap: 20 }}>
      {items.map((it, i) => (
        <div key={i} className="opa-card" style={{ padding: 26, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <span className="mono" style={{ fontSize: 13, color: 'var(--ink-3)' }}>{String(i + 1).padStart(2, '0')}</span>
          <h3 style={{ margin: 0, fontSize: 22, lineHeight: 1.2, fontWeight: 500, letterSpacing: '-0.02em' }}>{it.title}</h3>
          <p style={{ margin: 0, fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)', textWrap: 'pretty' }}>{it.body}</p>
        </div>
      ))}
    </div>
  );
}

/** Steps along a thin top rule. */
export function Steps({ items, min = 230 }: { items: Item[]; min?: number }) {
  return (
    <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(min(${min}px, 100%), 1fr))`, gap: '40px 0' }}>
      {items.map((it, i) => (
        <li key={i} style={{ borderTop: '1px solid var(--ink)', padding: '20px 28px 0 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span className="mono" style={{ fontSize: 13, color: 'var(--ink-3)' }}>Step {i + 1}</span>
          <span style={{ fontSize: 20, fontWeight: 500, letterSpacing: '-0.015em' }}>{it.title}</span>
          <span style={{ fontSize: 16, color: 'var(--ink-2)' }}>{it.body}</span>
        </li>
      ))}
    </ol>
  );
}

/** A framed list of label / value rows on the pale panel. */
export function KeyValue({ rows }: { rows: Array<{ k: string; v: ReactNode; tone?: 'stop' | 'ok' }> }) {
  return (
    <div className="frame2">
      <div className="frame2-in">
        {rows.map((r, i) => (
          <div key={r.k} style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 28px', padding: '16px 22px', borderBottom: i < rows.length - 1 ? '1px solid var(--line)' : 0 }}>
            <span style={{ flex: '0 0 200px', fontSize: 14, color: 'var(--ink-3)' }}>{r.k}</span>
            <span style={{ flex: '1 1 260px', minWidth: 0, fontSize: 16, fontWeight: r.tone ? 500 : 400, color: r.tone === 'stop' ? 'var(--stop)' : r.tone === 'ok' ? 'var(--ok)' : 'var(--ink)' }}>{r.v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** A screenshot in the framed panel. */
export function Shot({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="frame2" style={{ boxShadow: '0 40px 80px -50px rgba(28,27,24,0.3)' }}>
      <div className="frame2-in" style={{ aspectRatio: '16 / 10' }}>
        <img src={src} alt={alt} loading="lazy" style={{ display: 'block', width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top left' }} />
      </div>
    </div>
  );
}
