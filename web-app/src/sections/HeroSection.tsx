import { useEffect, useRef, useState } from 'react';

const TEAMS  = ['eng-platform','support-bot','research','finance','marketing','ext-partner'];
const MODELS = ['gpt-4o','claude-3.5-sonnet','gemini-1.5-pro','gpt-4o-mini','mistral-large-2','llama-3-70b','command-r+'];
const POLS: [string, 'ok'|'redact'|'cache'|'block'][] = [
  ['','ok'],['','ok'],['','ok'],['pii','redact'],['cache','cache'],['topic','block'],['','ok'],['','ok'],
];

interface FeedRow { time: string; team: string; model: string; tokens: string; lat: string; pol: string; pillKind: 'ok'|'redact'|'cache'|'block'; st: string; id: number; }

const STATUS_TEXT = { ok:'200 OK', cache:'CACHE', redact:'REDACT', block:'BLOCK 446' };

function makeRow(id: number, t = new Date()): FeedRow {
  const [pol, pillKind] = POLS[Math.floor(Math.random() * POLS.length)];
  const hh = String(t.getHours()).padStart(2,'0');
  const mm = String(t.getMinutes()).padStart(2,'0');
  const ss = String(t.getSeconds()).padStart(2,'0');
  const ms = String(t.getMilliseconds()).padStart(3,'0');
  return {
    id,
    time: `${hh}:${mm}:${ss}.${ms}`,
    team: TEAMS[Math.floor(Math.random() * TEAMS.length)],
    model: MODELS[Math.floor(Math.random() * MODELS.length)],
    tokens: (100 + Math.floor(Math.random() * 3500)).toLocaleString(),
    lat: (Math.random() < 0.2 ? Math.floor(Math.random()*40+20) : Math.floor(Math.random()*800+400)) + 'ms',
    pol,
    pillKind,
    st: STATUS_TEXT[pillKind],
  };
}

const PILL_CLASS: Record<string,'ok'|'redact'|'cache'|'block'> = { ok:'ok', redact:'redact', cache:'cache', block:'block' };

export default function HeroSection() {
  const [rows, setRows] = useState<FeedRow[]>(() => {
    const now = new Date();
    return Array.from({ length: 14 }, (_, i) => makeRow(i, new Date(now.getTime() - i * 1800)));
  });
  const [newId, setNewId] = useState<number | null>(null);
  const [rps, setRps] = useState(214);
  const idRef = useRef(100);

  useEffect(() => {
    const feedInt = setInterval(() => {
      const id = idRef.current++;
      setNewId(id);
      setRows(prev => [makeRow(id), ...prev].slice(0, 20));
    }, 900);
    const rpsInt = setInterval(() => {
      setRps(214 + Math.floor((Math.random() - 0.5) * 40));
    }, 500);
    return () => { clearInterval(feedInt); clearInterval(rpsInt); };
  }, []);

  const wrap: React.CSSProperties = { maxWidth: 1380, margin: '0 auto', padding: '0 24px' };

  return (
    <div style={{ ...wrap, padding: '28px 24px 36px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1.25fr 2fr', gap: 20 }} className="hero-grid">

        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Headline card */}
          <div style={{
            padding: '28px 24px 24px',
            display: 'flex', flexDirection: 'column', gap: 16,
            border: '1px solid var(--line)', borderRadius: 10,
            background: 'radial-gradient(ellipse 80% 100% at 80% 0%, color-mix(in srgb, var(--accent) 10%, transparent) 0%, transparent 60%), var(--panel)',
          }}>
            <span style={{ fontSize: 11, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.2em', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 6, height: 6, background: 'var(--accent)', borderRadius: '50%', display: 'inline-block' }} />
              LIVE · v2.4.1 · SOC 2 Type II
            </span>
            <h1 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(34px,3.8vw,54px)', lineHeight: 1.02, letterSpacing: '-0.03em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
              The <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>control plane</em> for enterprise AI. One gateway. Every model. Every audit.
            </h1>
            <p style={{ fontFamily: 'var(--sans)', fontSize: 15, lineHeight: 1.55, color: 'var(--ink-2)', margin: 0, maxWidth: '52ch' }}>
              OpenProxyAI routes, governs, and logs every LLM call across your org. 1,600+ models behind one API — with policy enforcement, PII redaction, cost attribution, and a replay-able audit trail.
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <a href="#" className="opa-btn opa-btn-primary">$ start trial →</a>
              <a href="#" className="opa-btn">$ curl examples</a>
            </div>
          </div>

          {/* KPI grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>
            {/* RPS */}
            <div className="opa-card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--ink-3)' }}>req/sec · live</span>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 26, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
                {rps}<span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)', marginLeft: 4 }}>rps</span>
              </span>
              <svg viewBox="0 0 100 24" style={{ height: 24, marginTop: 4 }} preserveAspectRatio="none">
                <polyline fill="none" stroke="var(--accent)" strokeWidth="1.5" points="0,20 10,18 20,14 30,16 40,10 50,12 60,7 70,9 80,4 90,6 100,3" />
              </svg>
            </div>
            {/* Overhead */}
            <div className="opa-card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--ink-3)' }}>overhead · p50</span>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 26, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
                3.8<span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)', marginLeft: 4 }}>ms</span>
              </span>
              <span style={{ fontSize: 11, color: 'var(--accent)' }}>▲ 0.2ms stable</span>
            </div>
            {/* Spend */}
            <div className="opa-card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--ink-3)' }}>spend · 24h</span>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 26, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>$1,284</span>
              <span style={{ fontSize: 11, color: 'var(--warn)' }}>▼ 4.1%</span>
            </div>
            {/* Cache */}
            <div className="opa-card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--ink-3)' }}>cache hit</span>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 26, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
                41.3<span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)', marginLeft: 4 }}>%</span>
              </span>
              <span style={{ fontSize: 11, color: 'var(--accent)' }}>▲ 3.0 pts</span>
            </div>
          </div>

          {/* Regions */}
          <div className="opa-card">
            <div className="opa-card-head">
              <span>regions</span>
              <span style={{ color: 'var(--ink-3)' }}>autoscaling</span>
            </div>
            <div style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
              {[
                { name: 'us-east-1', status: 'healthy', rps: 142, pct: 78, warn: false },
                { name: 'eu-west-1', status: 'healthy', rps: 54,  pct: 52, warn: false },
                { name: 'ap-south-1',status: 'degraded',rps: 18,  pct: 22, warn: true  },
              ].map(r => (
                <div key={r.name} style={{ border: '1px solid var(--line)', borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 6, background: 'var(--panel-2)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                    <span>{r.name}</span>
                    <span style={{ color: r.warn ? 'var(--warn)' : 'var(--accent)' }}>{r.status}</span>
                  </div>
                  <span style={{ fontFamily: 'var(--sans)', fontSize: 22, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
                    {r.rps}<span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-3)' }}> rps</span>
                  </span>
                  <div style={{ height: 3, background: 'var(--line)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${r.pct}%`, background: r.warn ? 'var(--warn)' : 'var(--accent)' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: live feed */}
        <div className="opa-card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 500 }}>
          <div className="opa-card-head">
            <span>request stream · api.openproxy.ai/v1/*</span>
            <span style={{ display: 'flex', gap: 10, alignItems: 'center', color: 'var(--ink-3)' }}>
              <span style={{ color: 'var(--accent)' }} className="live-dot">LIVE</span>
              <span>wss://stream</span>
            </span>
          </div>
          <div style={{ overflow: 'hidden', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11.5 }}>
              <thead>
                <tr>
                  {['time','team','model','tokens','lat','policy','status'].map(h => (
                    <th key={h} style={{ textAlign: 'left', fontWeight: 400, color: 'var(--ink-3)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.15em', padding: '8px 10px', borderBottom: '1px solid var(--line)', background: 'var(--panel-2)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id} className={r.id === newId ? 'row-new' : ''}>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>{r.time}</td>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', color: 'var(--accent)' }}>{r.team}</td>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', color: 'var(--ink)' }}>{r.model}</td>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', color: 'var(--ink-2)' }}>{r.tokens}</td>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', color: 'var(--ink-2)' }}>{r.lat}</td>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)' }}>
                      {r.pol
                        ? <span className={`pill pill-${PILL_CLASS[r.pillKind]}`}>{r.pol}</span>
                        : <span style={{ color: 'var(--ink-3)' }}>—</span>}
                    </td>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)' }}>
                      <span className={`pill pill-${PILL_CLASS[r.pillKind]}`}>{r.st}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .hero-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
