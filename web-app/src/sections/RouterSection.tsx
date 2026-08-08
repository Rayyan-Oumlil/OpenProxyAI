import { PAGE_MAX_WIDTH } from '../lib/layout';

const ROUTERS = [
  { name: 'openai · gpt-4o',              rps: 46, lat: '168ms p50', s: 'ok'   },
  { name: 'anthropic · claude-3.5-sonnet',rps: 22, lat: '240ms p50', s: 'ok'   },
  { name: 'google · gemini-1.5-pro',      rps: 13, lat: '201ms p50', s: 'ok'   },
  { name: 'azure · gpt-4-turbo',          rps: 9,  lat: '195ms p50', s: 'ok'   },
  { name: 'mistral · large-2',            rps: 7,  lat: '312ms p50', s: 'ok'   },
  { name: 'cohere · command-r+',          rps: 5,  lat: '288ms p50', s: 'ok'   },
  { name: 'meta · llama-3-70b',           rps: 4,  lat: '421ms p50', s: 'warn' },
  { name: 'groq · mixtral',               rps: 3,  lat: '88ms p50',  s: 'ok'   },
];

const TOTAL_RPS = ROUTERS.reduce((sum, r) => sum + r.rps, 0);
const MAX_RPS = Math.max(...ROUTERS.map(r => r.rps));

export default function RouterSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§02 · provider router</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Sixteen hundred models. <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>Weighted rotation,</em> per-region failover.
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>live health</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 40 }} className="router-layout">
          {/* Big stat */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(52px,5.5vw,76px)', fontWeight: 500, letterSpacing: '-0.03em', color: 'var(--ink)', lineHeight: 1 }}>{TOTAL_RPS}</span>
            <span style={{ fontSize: 12, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.15em' }}>requests / sec</span>
            <span style={{ fontSize: 12, color: 'var(--accent)', marginTop: 12 }}>8 providers · 0 downtime</span>
          </div>

          {/* Share bar + ranked list */}
          <div>
            <div style={{ display: 'flex', height: 26, borderRadius: 6, overflow: 'hidden', border: '1px solid var(--line)' }}>
              {ROUTERS.map(r => (
                <div key={r.name} title={`${r.name} · ${Math.round((r.rps / TOTAL_RPS) * 100)}%`} style={{
                  width: `${(r.rps / TOTAL_RPS) * 100}%`,
                  background: r.s === 'warn' ? 'var(--warn)' : 'var(--accent)',
                  opacity: 0.32 + (r.rps / MAX_RPS) * 0.68,
                  borderRight: '1px solid var(--bg)',
                }} />
              ))}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {ROUTERS.map((r, i) => (
                <div key={r.name} style={{
                  display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 16, alignItems: 'center',
                  padding: '10px 0', borderTop: i === 0 ? 'none' : '1px solid var(--line)', fontSize: 12.5, marginTop: i === 0 ? 14 : 0,
                }}>
                  <span style={{ color: 'var(--ink)' }}>{r.name}</span>
                  <span style={{ color: 'var(--ink-3)' }}>{r.lat}</span>
                  <span style={{ color: r.s === 'warn' ? 'var(--warn)' : 'var(--accent)', fontVariantNumeric: 'tabular-nums', minWidth: 56, textAlign: 'right' }}>{r.rps} rps</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .router-layout { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
