import { PAGE_MAX_WIDTH } from '../lib/layout';

const HOPS = [
  { n: '1', title: 'Your app', desc: 'Calls the OpenAI-compatible endpoint using your existing SDK — no new client library required.' },
  { n: '2', title: 'OpenProxyAI', desc: 'Auths, rate-limits, applies policy, checks cache, and picks a provider — all inside your own VPC.' },
  { n: '3', title: 'Provider', desc: 'OpenAI, Anthropic, Azure, Mistral, or any of 1,600+ models — routed to on your behalf, never hardcoded in your app.' },
];

export default function ArchitectureSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§01 · architecture</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Three hops. <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>Nothing hardcoded.</em>
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>self-hosted · your vpc</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 28 }} className="arch-grid">
          {HOPS.map(h => (
            <div key={h.n} className="opa-card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 22, fontWeight: 500, color: 'var(--accent)' }}>{h.n}</span>
              <span style={{ color: 'var(--ink)', fontSize: 14, fontWeight: 500 }}>{h.title}</span>
              <p style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6, margin: 0 }}>{h.desc}</p>
            </div>
          ))}
        </div>

        <p style={{ color: 'var(--ink-2)', fontSize: 14, lineHeight: 1.7, maxWidth: '68ch', margin: 0 }}>
          The proxy runs as a single stateless service in front of Postgres and Redis — no message queue, no separate control-plane cluster. It scales horizontally behind a load balancer like any other API service, and every instance shares the same cache and rate-limit state through Redis.
        </p>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
          .arch-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
