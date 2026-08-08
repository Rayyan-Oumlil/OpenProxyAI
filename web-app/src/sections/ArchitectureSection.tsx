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

        <div className="opa-card" style={{ padding: '28px 20px', marginBottom: 20, overflow: 'auto' }}>
          <svg viewBox="0 0 860 260" style={{ width: '100%', height: 'auto', minWidth: 640 }} role="img" aria-label="Architecture diagram: your app connects to OpenProxyAI, which connects to Postgres and Redis and routes to provider APIs">
            {/* Your app */}
            <rect x="20" y="105" width="140" height="50" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="90" y="135" textAnchor="middle" fontFamily="var(--mono)" fontSize="13" fill="var(--ink)">Your app</text>

            {/* Arrow app -> proxy */}
            <line x1="160" y1="130" x2="228" y2="130" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />

            {/* OpenProxyAI */}
            <rect x="230" y="80" width="180" height="100" rx="8" fill="var(--panel)" stroke="var(--accent)" strokeWidth="1.5" />
            <text x="320" y="120" textAnchor="middle" fontFamily="var(--sans)" fontSize="14" fontWeight="500" fill="var(--ink)">OpenProxyAI</text>
            <text x="320" y="140" textAnchor="middle" fontFamily="var(--mono)" fontSize="10.5" fill="var(--ink-3)">auth · policy · cache</text>
            <text x="320" y="155" textAnchor="middle" fontFamily="var(--mono)" fontSize="10.5" fill="var(--ink-3)">route · log</text>

            {/* Down arrows to postgres/redis */}
            <line x1="290" y1="180" x2="270" y2="210" stroke="var(--line-2)" strokeWidth="1.5" markerEnd="url(#arrowmuted)" />
            <line x1="350" y1="180" x2="370" y2="210" stroke="var(--line-2)" strokeWidth="1.5" markerEnd="url(#arrowmuted)" />
            <rect x="210" y="212" width="110" height="36" rx="6" fill="var(--panel-2)" stroke="var(--line)" />
            <text x="265" y="234" textAnchor="middle" fontFamily="var(--mono)" fontSize="11" fill="var(--ink-2)">Postgres</text>
            <rect x="330" y="212" width="110" height="36" rx="6" fill="var(--panel-2)" stroke="var(--line)" />
            <text x="385" y="234" textAnchor="middle" fontFamily="var(--mono)" fontSize="11" fill="var(--ink-2)">Redis</text>

            {/* Arrows proxy -> providers */}
            <line x1="410" y1="105" x2="618" y2="45" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />
            <line x1="410" y1="120" x2="618" y2="95" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />
            <line x1="410" y1="140" x2="618" y2="150" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />
            <line x1="410" y1="155" x2="618" y2="200" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />

            {/* Provider boxes */}
            <rect x="620" y="20" width="160" height="42" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="700" y="46" textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">OpenAI</text>
            <rect x="620" y="72" width="160" height="42" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="700" y="98" textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">Anthropic</text>
            <rect x="620" y="124" width="160" height="42" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="700" y="150" textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">Azure</text>
            <rect x="620" y="176" width="160" height="42" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="700" y="202" textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">Mistral + more</text>

            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 Z" fill="var(--accent)" />
              </marker>
              <marker id="arrowmuted" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 Z" fill="var(--line-2)" />
              </marker>
            </defs>
          </svg>
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
