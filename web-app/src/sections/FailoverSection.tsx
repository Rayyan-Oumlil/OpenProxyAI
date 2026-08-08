import { PAGE_MAX_WIDTH } from '../lib/layout';

const STEPS = [
  { t: 'Key #3 starts erroring', d: 'Provider returns elevated 5xx or rate-limit responses on key #3 for gpt-4o.' },
  { t: 'Router marks it unhealthy', d: 'Health check state updates within one polling interval — key #3 is excluded from the weighted-rotation candidate set.' },
  { t: 'Traffic redistributes', d: 'Remaining healthy keys absorb the load, reweighted proportionally. No client-visible errors, no retry logic needed in your app.' },
  { t: 'Key #3 recovers', d: 'Once health checks pass again, it re-enters rotation at its configured weight — no manual intervention required.' },
];

export default function FailoverSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§02 · failover</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            One key dies. <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>Nobody notices.</em>
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>example scenario</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {STEPS.map((s, i) => (
            <div key={s.t} style={{ display: 'grid', gridTemplateColumns: '32px 1fr', gap: 14, padding: '12px 0', borderBottom: i < STEPS.length - 1 ? '1px solid var(--line)' : 'none' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--accent)' }}>{String(i + 1).padStart(2, '0')}</span>
              <div>
                <div style={{ color: 'var(--ink)', fontSize: 13, fontWeight: 500, marginBottom: 2 }}>{s.t}</div>
                <div style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6 }}>{s.d}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
