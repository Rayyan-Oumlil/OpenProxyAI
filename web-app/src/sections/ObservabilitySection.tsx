import { PAGE_MAX_WIDTH } from '../lib/layout';

const SIGNALS = [
  { name: 'Prometheus', desc: 'A /metrics endpoint exposes request rate, latency, cache hit rate, and error rate per provider — scrape it with your existing stack.' },
  { name: 'Structured logs', desc: 'Every log line is JSON — request ID, org, latency breakdown by pipeline stage — built to be piped straight into your log aggregator.' },
  { name: 'Request tracing', desc: 'Trace a single request across every pipeline stage, including which cache tier served it and why a policy fired.' },
];

export default function ObservabilitySection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§03 · observability</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Plugs into <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>what you already run.</em>
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>opt-in per deployment</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }} className="obs-grid">
          {SIGNALS.map(s => (
            <div key={s.name} style={{ padding: 18, border: '1px solid var(--line)', borderRadius: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span style={{ color: 'var(--ink)', fontSize: 13, fontWeight: 500 }}>{s.name}</span>
              <p style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6, margin: 0 }}>{s.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
          .obs-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
