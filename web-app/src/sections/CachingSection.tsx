import { PAGE_MAX_WIDTH } from '../lib/layout';

const TIERS = [
  { n: 'L1', name: 'In-memory', desc: 'Per-instance TTL cache. Sub-millisecond hits for exact repeat requests within the same proxy process.', lat: '<1ms', pct: 16 },
  { n: 'L2', name: 'Redis', desc: 'Shared cache across every proxy instance. Exact-match hits survive restarts and scale horizontally.', lat: '~2ms', pct: 23 },
  { n: 'L3', name: 'Semantic (pgvector)', desc: 'Embeds each prompt and matches on similarity, not exact text — catches paraphrased requests the first two tiers miss.', lat: '~40ms', pct: 100 },
];

export default function CachingSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }} id="caching">
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 40, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§02 · caching</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Three tiers. <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>Fewer duplicate calls,</em> lower cost.
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>checked in order</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 22, maxWidth: 860 }}>
          {TIERS.map(t => (
            <div key={t.n}>
              <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr 56px', gap: 14, alignItems: 'center', marginBottom: 7 }}>
                <span style={{ fontFamily: 'var(--sans)', fontSize: 17, fontWeight: 500, color: 'var(--accent)' }}>{t.n}</span>
                <div style={{ height: 7, background: 'var(--line)', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${t.pct}%`, background: 'var(--accent)', opacity: 0.45 + (t.pct / 200) }} />
                </div>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)', textAlign: 'right' }}>{t.lat}</span>
              </div>
              <div style={{ paddingLeft: 54, fontSize: 13, lineHeight: 1.6 }}>
                <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{t.name}</span>
                <span style={{ color: 'var(--ink-2)' }}> — {t.desc}</span>
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
