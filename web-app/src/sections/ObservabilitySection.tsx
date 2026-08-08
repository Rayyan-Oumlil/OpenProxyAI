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

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 36 }} className="obs-grid">
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {SIGNALS.map((s, i) => (
              <div key={s.name} style={{ padding: '16px 0', borderTop: i === 0 ? 'none' : '1px solid var(--line)' }}>
                <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500, marginBottom: 5 }}>{s.name}</div>
                <p style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6, margin: 0 }}>{s.desc}</p>
              </div>
            ))}
          </div>

          <div className="opa-card">
            <div className="opa-card-head"><span>GET /metrics</span><span>prometheus · text</span></div>
            <pre style={{ padding: 18, fontSize: 12, lineHeight: 1.8, color: 'var(--ink)', overflow: 'auto' }}>
              <span style={{ color: 'var(--ink-3)' }}>{'# HELP openproxy_request_latency_ms proxy overhead per stage\n'}</span>
              <span style={{ color: 'var(--ink-3)' }}>{'# TYPE openproxy_request_latency_ms histogram\n'}</span>
              openproxy_request_latency_ms{'{'}<span style={{ color: '#c7a2ff' }}>stage</span>=<span style={{ color: '#8bc6ff' }}>"policy"</span>{'}'} <span style={{ color: '#ffc66a' }}>0.8</span>{'\n'}
              openproxy_request_latency_ms{'{'}<span style={{ color: '#c7a2ff' }}>stage</span>=<span style={{ color: '#8bc6ff' }}>"cache"</span>{'}'} <span style={{ color: '#ffc66a' }}>0.4</span>{'\n'}
              openproxy_cache_hit_ratio{'{'}<span style={{ color: '#c7a2ff' }}>tier</span>=<span style={{ color: '#8bc6ff' }}>"L2"</span>{'}'} <span style={{ color: '#ffc66a' }}>0.31</span>{'\n'}
              openproxy_requests_total{'{'}<span style={{ color: '#c7a2ff' }}>provider</span>=<span style={{ color: '#8bc6ff' }}>"openai"</span>{'}'} <span style={{ color: '#ffc66a' }}>48213</span>{'\n'}
              openproxy_errors_total{'{'}<span style={{ color: '#c7a2ff' }}>provider</span>=<span style={{ color: '#8bc6ff' }}>"meta"</span>{'}'} <span style={{ color: 'var(--warn)' }}>12</span>
            </pre>
          </div>
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
