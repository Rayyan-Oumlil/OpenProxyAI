import { useEffect, useState } from 'react';
import { PAGE_MAX_WIDTH } from '../lib/layout';

const STEPS = [
  { n: '01 · AUTH',   t: 'verify key',         d: '0.2ms · jwt' },
  { n: '02 · RATE',   t: 'limit check',        d: '0.1ms · 423/3000' },
  { n: '03 · POLICY', t: 'redact · guard',     d: '0.8ms · 2 hits' },
  { n: '04 · CACHE',  t: 'L1 · L2 · L3',       d: '0.4ms · miss' },
  { n: '05 · ROUTE',  t: 'gpt-4o · key#3',     d: 'us-east · weighted' },
  { n: '06 · LOG',    t: 'async · fire&forget', d: 'clickhouse + s3' },
];

const SEC: React.CSSProperties = {
  padding: '60px 0',
  borderTop: '1px solid var(--line)',
};
const WRAP: React.CSSProperties = { maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' };

export default function PipelineSection() {
  const [hot, setHot] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setHot(h => (h + 1) % STEPS.length), 700);
    return () => clearInterval(t);
  }, []);

  return (
    <section style={SEC}>
      <div style={WRAP}>
        {/* Section header */}
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§01 · request pipeline</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Every request, <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>seven checks,</em> under four milliseconds.
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>measured · p50 overhead</span>
        </div>

        {/* Pipeline steps */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 8, marginBottom: 28 }} className="pipe-grid">
          {STEPS.map((s, i) => (
            <div key={i} className={hot === i ? 'pipe-hot' : ''} style={{
              border: '1px solid var(--line)', borderRadius: 8, padding: 14,
              background: 'var(--panel)', display: 'flex', flexDirection: 'column', gap: 8,
              position: 'relative', transition: 'border-color .2s, background .2s, transform .2s',
            }}>
              {i < STEPS.length - 1 && (
                <span style={{ position: 'absolute', right: -10, top: '50%', width: 10, height: 1, background: 'var(--line-2)' }} />
              )}
              <span className="pipe-n" style={{ fontSize: 10, color: 'var(--ink-3)', letterSpacing: '0.2em' }}>{s.n}</span>
              <span style={{ color: 'var(--ink)', fontSize: 13 }}>{s.t}</span>
              <span style={{ color: 'var(--ink-3)', fontSize: 11 }}>{s.d}</span>
            </div>
          ))}
        </div>

        {/* Console panels */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }} className="console-grid">
          <div className="opa-card">
            <div className="opa-card-head"><span>POST /v1/chat/completions</span><span>t+0.00ms</span></div>
            <pre style={{ padding: '18px', fontSize: 12.5, lineHeight: 1.7, color: 'var(--ink)', overflow: 'auto', maxHeight: 380 }}><span style={{ color: 'var(--ink-3)' }}>{'// client request'}</span>
{`POST `}<span style={{ color: '#8bc6ff' }}>/v1/chat/completions</span>{` HTTP/2
`}<span style={{ color: '#c7a2ff' }}>host</span>{`:          api.openproxy.ai
`}<span style={{ color: '#c7a2ff' }}>authorization</span>{`: Bearer sk_live_***
`}<span style={{ color: '#c7a2ff' }}>x-op-team</span>{`:     `}<span style={{ color: '#8bc6ff' }}>eng-platform</span>{`
`}<span style={{ color: '#c7a2ff' }}>x-op-policy</span>{`:   `}<span style={{ color: '#8bc6ff' }}>pii_redact,topic_guard</span>{`

{
  `}<span style={{ color: '#c7a2ff' }}>"model"</span>{`:    `}<span style={{ color: '#8bc6ff' }}>"gpt-4o"</span>{`,
  `}<span style={{ color: '#c7a2ff' }}>"messages"</span>{`: [
    { `}<span style={{ color: '#c7a2ff' }}>"role"</span>{`: `}<span style={{ color: '#8bc6ff' }}>"user"</span>{`,
      `}<span style={{ color: '#c7a2ff' }}>"content"</span>{`: `}<span style={{ color: '#8bc6ff' }}>"Summarize for me@acme.com"</span>{` }
  ],
  `}<span style={{ color: '#c7a2ff' }}>"stream"</span>{`:  `}<span style={{ color: '#ffc66a' }}>true</span>{`
}`}
            </pre>
          </div>
          <div className="opa-card">
            <div className="opa-card-head"><span>proxy trace · req_01J3K9A2XM</span><span>t+3.8ms</span></div>
            <pre style={{ padding: '18px', fontSize: 12.5, lineHeight: 1.7, color: 'var(--ink)', overflow: 'auto', maxHeight: 380 }}><span style={{ color: 'var(--accent)' }}>✓</span>{` `}<span style={{ color: '#c7a2ff' }}>auth</span>{`       `}<span style={{ color: 'var(--ink-3)' }}>jwt · user=m.patel · org=acme</span>{`
`}<span style={{ color: 'var(--accent)' }}>✓</span>{` `}<span style={{ color: '#c7a2ff' }}>rate_limit</span>{` `}<span style={{ color: 'var(--ink-3)' }}>423/3000 rpm · 89/100k tpm</span>{`
`}<span style={{ color: 'var(--warn)' }}>◉</span>{` `}<span style={{ color: '#c7a2ff' }}>policy</span>{`     `}<span style={{ color: 'var(--ink-3)' }}>pii_redact: 1 span · topic_guard: pass</span>{`
`}<span style={{ color: 'var(--accent)' }}>✓</span>{` `}<span style={{ color: '#c7a2ff' }}>cache</span>{`      `}<span style={{ color: 'var(--ink-3)' }}>L1 miss · L2 miss · L3 sim=0.72 (miss)</span>{`
`}<span style={{ color: 'var(--accent)' }}>✓</span>{` `}<span style={{ color: '#c7a2ff' }}>route</span>{`      `}<span style={{ color: 'var(--ink-3)' }}>gpt-4o · key#3 · weight=0.7 · us-east</span>{`
`}<span style={{ color: 'var(--accent)' }}>✓</span>{` `}<span style={{ color: '#c7a2ff' }}>upstream</span>{`   `}<span style={{ color: 'var(--ink-3)' }}>openai · 200 · ttft=168ms</span>{`
`}<span style={{ color: 'var(--accent)' }}>✓</span>{` `}<span style={{ color: '#c7a2ff' }}>log</span>{`        `}<span style={{ color: 'var(--ink-3)' }}>async · clickhouse + s3</span>{`

`}<span style={{ color: 'var(--ink-3)' }}>{'// decision'}</span>{`
{
  `}<span style={{ color: '#c7a2ff' }}>"forwarded"</span>{`: `}<span style={{ color: '#ffc66a' }}>true</span>{`,
  `}<span style={{ color: '#c7a2ff' }}>"redactions"</span>{`: `}<span style={{ color: '#ffc66a' }}>1</span>{`,
  `}<span style={{ color: '#c7a2ff' }}>"cost_usd"</span>{`: `}<span style={{ color: '#ffc66a' }}>0.0124</span>{`,
  `}<span style={{ color: '#c7a2ff' }}>"latency_ms"</span>{`: { `}<span style={{ color: '#c7a2ff' }}>"proxy"</span>{`: `}<span style={{ color: '#ffc66a' }}>3.8</span>{`, `}<span style={{ color: '#c7a2ff' }}>"total"</span>{`: `}<span style={{ color: '#ffc66a' }}>1812</span>{` }
}`}
            </pre>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
          .pipe-grid { grid-template-columns: repeat(2,1fr) !important; }
          .console-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
