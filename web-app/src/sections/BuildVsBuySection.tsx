import { PAGE_MAX_WIDTH } from '../lib/layout';

const ROWS = [
  { item: 'Multi-provider routing + failover', build: '2-4 weeks eng time', buy: 'included' },
  { item: 'PII redaction & policy engine', build: '3-6 weeks + ongoing tuning', buy: 'included' },
  { item: 'Immutable audit log + compliance export', build: '2-3 weeks', buy: 'included' },
  { item: 'Semantic caching', build: '2-4 weeks', buy: 'included' },
  { item: 'Ongoing maintenance as providers change', build: 'indefinite', buy: 'included' },
];

export default function BuildVsBuySection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§01 · build vs. buy</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            What this replaces on <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>your roadmap.</em>
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>rough estimate</span>
        </div>

        <div className="opa-card">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px 140px', gap: 16, padding: '10px 18px', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.1em', borderBottom: '1px solid var(--line)', background: 'var(--panel-2)' }} className="bvb-head">
            <span>capability</span>
            <span>build it yourself</span>
            <span>with openproxyai</span>
          </div>
          {ROWS.map((r, i) => (
            <div key={r.item} style={{
              display: 'grid', gridTemplateColumns: '1fr 200px 140px', gap: 16, padding: '14px 18px',
              borderBottom: i < ROWS.length - 1 ? '1px solid var(--line)' : 'none', fontSize: 13, alignItems: 'center',
            }} className="bvb-row">
              <span style={{ color: 'var(--ink)' }}>{r.item}</span>
              <span style={{ color: 'var(--ink-2)' }}>{r.build}</span>
              <span style={{ color: 'var(--accent)' }}>{r.buy}</span>
            </div>
          ))}
        </div>

        <p style={{ color: 'var(--ink-3)', fontSize: 12, margin: '14px 0 0' }}>
          Rough build estimates for a mid-size eng team — actual time varies. Doesn't include ongoing maintenance as provider APIs change.
        </p>
      </div>

      <style>{`
        @media (max-width: 700px) {
          .sec-head { grid-template-columns: 1fr !important; }
          .bvb-head, .bvb-row { grid-template-columns: 1fr !important; gap: 4px !important; }
        }
      `}</style>
    </section>
  );
}
