import { useEffect, useRef, useState } from 'react';
import { PAGE_MAX_WIDTH } from '../lib/layout';
import { APP_URL } from '../lib/links';

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
    return Array.from({ length: 11 }, (_, i) => makeRow(i, new Date(now.getTime() - i * 1800)));
  });
  const [newId, setNewId] = useState<number | null>(null);
  const idRef = useRef(100);

  useEffect(() => {
    const feedInt = setInterval(() => {
      const id = idRef.current++;
      setNewId(id);
      setRows(prev => [makeRow(id), ...prev].slice(0, 11));
    }, 900);
    return () => clearInterval(feedInt);
  }, []);

  const wrap: React.CSSProperties = { maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' };

  return (
    <div style={{ ...wrap, padding: '28px 24px 36px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1.25fr 2fr', gap: 20, alignItems: 'start' }} className="hero-grid">

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
              LIVE · v2.4.1
            </span>
            <h1 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(34px,3.8vw,54px)', lineHeight: 1.02, letterSpacing: '-0.03em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
              The <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>control plane</em> for enterprise AI. One gateway. Every model. Every audit.
            </h1>
            <p style={{ fontFamily: 'var(--sans)', fontSize: 15, lineHeight: 1.55, color: 'var(--ink-2)', margin: 0, maxWidth: '52ch' }}>
              OpenProxyAI routes, governs, and logs every LLM call across your org. 1,600+ models behind one API — with policy enforcement, PII redaction, cost attribution, and a replay-able audit trail.
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <a href={APP_URL} className="opa-btn opa-btn-primary">$ start trial →</a>
              <a href="#deploy" className="opa-btn">$ curl examples</a>
            </div>
          </div>

        </div>

        {/* Right: live feed */}
        <div className="opa-card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
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
