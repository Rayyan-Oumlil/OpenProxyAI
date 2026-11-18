import { useEffect, useState } from 'react';
import type { MouseEvent } from 'react';

const SHOTS = [
  { label: 'Dashboard', note: 'What was allowed, flagged and stopped, at a glance.', src: '/images/console/dashboard.webp', alt: 'OpenProxyAI console dashboard: requests, cost, how many requests were stopped or flagged by policy, and budget for the month.' },
  { label: 'Policy', note: 'The rules for the whole organization, set in one place.', src: '/images/console/policy.webp', alt: 'OpenProxyAI policy screen: enforcement mode, the list of allowed models, and blocked keywords.' },
  { label: 'Request record', note: 'Any single decision, opened up: what was found and what the person was told.', src: '/images/console/trace.webp', alt: 'OpenProxyAI request record: a request blocked because personal data was detected, what the caller was told, and the record number.' },
];

function setSpot(e: MouseEvent<HTMLElement>) {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`);
}

interface ConsoleSectionProps { eyebrow?: string; title?: string; lede?: string }

export default function ConsoleSection({ eyebrow = 'The console', title = 'This is the real product, not a drawing of it.', lede = 'These are screens from the OpenProxyAI console your team would use, shown with sample data.' }: ConsoleSectionProps) {
  const [shot, setShot] = useState(0);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const t = window.setInterval(() => setShot(s => (s + 1) % SHOTS.length), 6000);
    return () => window.clearInterval(t);
  }, [tick]);

  return (
    <section id="console" aria-labelledby="console-title" style={{ padding: '0 24px', borderTop: '1px solid var(--line)', background: '#fff', scrollMarginTop: 110 }}>
      <div className="rail" style={{ maxWidth: 1240, margin: '0 auto', padding: '112px clamp(20px, 4vw, 56px)', display: 'flex', flexDirection: 'column', gap: 48 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px 72px', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div style={{ flex: '1.4 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 20 }}>
            <p className="eyebrow">{eyebrow}</p>
            <h2 id="console-title" style={{ margin: 0, fontSize: 'clamp(32px, 3.8vw, 52px)', lineHeight: 1.06, fontWeight: 500, letterSpacing: '-0.032em', textWrap: 'balance' }}>{title}</h2>
          </div>
          <p style={{ flex: '1 1 320px', minWidth: 0, margin: 0, color: 'var(--ink-2)', textWrap: 'pretty' }}>{lede}</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(250px, 100%), 1fr))', gap: '8px 32px' }}>
          {SHOTS.map((s, i) => (
            <button key={s.label} type="button" className={`shot-tab${i === shot ? ' on' : ''}`} aria-pressed={i === shot} onClick={() => { setShot(i); setTick(t => t + 1); }}
              style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 6, textAlign: 'left', background: 'none', border: 0, borderTop: '1px solid var(--line-2)', padding: '18px 0 10px', minHeight: 56, cursor: 'pointer', fontFamily: 'inherit' }}>
              <span className="fill" aria-hidden="true" style={{ position: 'absolute', top: -1, left: 0, right: 0, height: 2, background: 'var(--ink)' }} />
              <span style={{ fontSize: 19, fontWeight: 500, letterSpacing: '-0.015em' }}>{s.label}</span>
              <span style={{ fontSize: 15, lineHeight: 1.5, color: 'var(--ink-2)' }}>{s.note}</span>
            </button>
          ))}
        </div>
        <div className="spot frame2 shotframe" onMouseMove={setSpot} style={{ boxShadow: '0 40px 80px -50px rgba(28,27,24,0.3)' }}>
          <div className="frame2-in" style={{ position: 'relative', aspectRatio: '16 / 10' }}>
            {SHOTS.map((s, i) => (
              <img key={s.src} className={`shot${i === shot ? ' on' : ''}`} src={s.src} alt={s.alt} loading="lazy"
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top left' }} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
