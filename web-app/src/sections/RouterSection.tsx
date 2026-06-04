const ROUTERS = [
  { name: 'openai · gpt-4o',             sig: 'stable', rps: 142, lat: '168ms p50', pct: 92, keys: [1,1,1,1],   s: 'ok'   },
  { name: 'anthropic · claude-3.5-sonnet',sig: 'stable', rps: 54,  lat: '240ms p50', pct: 88, keys: [1,1,1,0],   s: 'ok'   },
  { name: 'google · gemini-1.5-pro',      sig: 'stable', rps: 31,  lat: '201ms p50', pct: 71, keys: [1,1,1],     s: 'ok'   },
  { name: 'azure · gpt-4-turbo',          sig: 'stable', rps: 24,  lat: '195ms p50', pct: 64, keys: [1,1],       s: 'ok'   },
  { name: 'mistral · large-2',            sig: 'stable', rps: 18,  lat: '312ms p50', pct: 52, keys: [1,1,1],     s: 'ok'   },
  { name: 'cohere · command-r+',          sig: 'stable', rps: 14,  lat: '288ms p50', pct: 46, keys: [1,1],       s: 'ok'   },
  { name: 'meta · llama-3-70b',           sig: 'warn',   rps: 11,  lat: '421ms p50', pct: 38, keys: [1,0,1],     s: 'warn' },
  { name: 'groq · mixtral',               sig: 'stable', rps: 8,   lat: '88ms p50',  pct: 22, keys: [1,1],       s: 'ok'   },
];

export default function RouterSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: 1380, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§02 · provider router</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Sixteen hundred models. <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>Weighted rotation,</em> per-region failover.
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>live health</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }} className="router-grid">
          {ROUTERS.map(r => (
            <div key={r.name} className="opa-card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--ink)', fontSize: 13 }}>
                  {r.name}
                  <span style={{ color: 'var(--ink-3)', fontSize: 11, marginLeft: 6 }}>· {r.sig}</span>
                </span>
              </div>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 20, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
                {r.rps}<span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-3)' }}> rps</span>
              </span>
              <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>{r.lat}</span>
              <div style={{ height: 3, background: 'var(--line)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${r.pct}%`, background: r.s === 'warn' ? 'var(--warn)' : 'var(--accent)' }} />
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                {r.keys.map((k, i) => (
                  <span key={i} style={{ width: 8, height: 8, borderRadius: 2, background: k ? 'var(--accent)' : 'var(--line-2)', opacity: k ? 0.85 : 1 }} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .router-grid { grid-template-columns: repeat(2,1fr) !important; }
        }
      `}</style>
    </section>
  );
}
