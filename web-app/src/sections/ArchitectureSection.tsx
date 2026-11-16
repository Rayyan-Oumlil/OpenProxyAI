import Section from '../components/Section';

const HOPS = [
  { n: '1', title: 'Your app', desc: 'Calls the OpenAI-compatible endpoint using your existing SDK. No new client library.' },
  { n: '2', title: 'OpenProxyAI', desc: 'Authenticates, rate-limits, applies policy, checks the cache and picks a provider, all inside your own environment.' },
  { n: '3', title: 'Provider', desc: 'OpenAI, Anthropic, Azure, Mistral and 100+ more through LiteLLM, including your own endpoints. The model choice is not hardcoded in your app.' },
];

export default function ArchitectureSection() {
  return (
    <Section id="architecture" label="§01 · architecture" title={<>Three hops. <em>Nothing hardcoded.</em></>} aside="self-hosted · your environment">
      <div className="opa-card" style={{ padding: '28px 20px', marginBottom: 8, overflow: 'auto' }}>
        <svg viewBox="0 0 860 260" style={{ width: '100%', height: 'auto', minWidth: 640 }} role="img" aria-label="Architecture diagram: your app connects to OpenProxyAI, which connects to Postgres and Redis and routes to provider APIs">
          <rect x="20" y="105" width="140" height="50" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
          <text x="90" y="135" textAnchor="middle" fontFamily="var(--mono)" fontSize="13" fill="var(--ink)">Your app</text>
          <line x1="160" y1="130" x2="228" y2="130" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />

          <rect x="230" y="80" width="180" height="100" rx="8" fill="var(--panel)" stroke="var(--accent)" strokeWidth="1.5" />
          <text x="320" y="120" textAnchor="middle" fontFamily="var(--sans)" fontSize="14" fontWeight="500" fill="var(--ink)">OpenProxyAI</text>
          <text x="320" y="140" textAnchor="middle" fontFamily="var(--mono)" fontSize="10.5" fill="var(--ink-3)">auth · policy · cache</text>
          <text x="320" y="155" textAnchor="middle" fontFamily="var(--mono)" fontSize="10.5" fill="var(--ink-3)">route · log</text>

          <line x1="290" y1="180" x2="270" y2="210" stroke="var(--line-2)" strokeWidth="1.5" markerEnd="url(#arrowmuted)" />
          <line x1="350" y1="180" x2="370" y2="210" stroke="var(--line-2)" strokeWidth="1.5" markerEnd="url(#arrowmuted)" />
          <rect x="210" y="212" width="110" height="36" rx="6" fill="var(--panel-2)" stroke="var(--line)" />
          <text x="265" y="234" textAnchor="middle" fontFamily="var(--mono)" fontSize="11" fill="var(--ink-2)">Postgres</text>
          <rect x="330" y="212" width="110" height="36" rx="6" fill="var(--panel-2)" stroke="var(--line)" />
          <text x="385" y="234" textAnchor="middle" fontFamily="var(--mono)" fontSize="11" fill="var(--ink-2)">Redis</text>

          <line x1="410" y1="105" x2="618" y2="45" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />
          <line x1="410" y1="120" x2="618" y2="95" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />
          <line x1="410" y1="140" x2="618" y2="150" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />
          <line x1="410" y1="155" x2="618" y2="200" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#arrow)" />

          <rect x="620" y="20" width="160" height="42" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
          <text x="700" y="46" textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">OpenAI</text>
          <rect x="620" y="72" width="160" height="42" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
          <text x="700" y="98" textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">Anthropic</text>
          <rect x="620" y="124" width="160" height="42" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
          <text x="700" y="150" textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">Azure</text>
          <rect x="620" y="176" width="160" height="42" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
          <text x="700" y="202" textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">Mistral + more</text>

          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--accent)" /></marker>
            <marker id="arrowmuted" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--line-2)" /></marker>
          </defs>
        </svg>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', marginBottom: 28 }}>
        {HOPS.map((h, i) => (
          <div key={h.n} className="hop-row" style={{ display: 'grid', gridTemplateColumns: '28px 150px minmax(0,1fr)', gap: 16, padding: '13px 0', borderTop: i === 0 ? 'none' : '1px solid var(--line)', alignItems: 'baseline' }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--accent)' }}>{h.n}</span>
            <span style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500 }}>{h.title}</span>
            <span style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6 }}>{h.desc}</span>
          </div>
        ))}
      </div>

      <p className="lede">
        The gateway runs as a stateless service in front of Postgres and Redis. It scales horizontally behind a load balancer, and every instance shares cache and rate-limit state through Redis.
      </p>
      <style>{`@media (max-width: 1000px) { .hop-row { grid-template-columns: minmax(0,1fr) !important; gap: 4px !important; } }`}</style>
    </Section>
  );
}
