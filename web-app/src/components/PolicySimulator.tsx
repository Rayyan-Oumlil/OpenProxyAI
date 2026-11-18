import { useCallback, useEffect, useRef, useState } from 'react';

interface Check { label: string; finding: string; ok: boolean }
interface Scenario {
  tab: string; who: string; via: string;
  pre: string; hot: string; post: string;
  checks: Check[]; ok: boolean; verdict: string; title: string; reason: string; why: string;
}
interface LogRow { key: number; time: string; who: string; decision: string; why: string; id: string; ok: boolean }

const SCENARIOS: Scenario[] = [
  {
    tab: 'Customer record in a chat', who: 'Claims analyst', via: 'Using the company chat assistant',
    pre: 'Summarize this claim for the file. Policyholder ', hot: 'Social Security number •••-••-••••', post: ', water damage, filed in March.',
    checks: [
      { label: 'Who is asking', finding: 'Claims analyst, signed in', ok: true },
      { label: 'What it contains', finding: 'A Social Security number', ok: false },
      { label: 'Where it is going', finding: 'A model not approved for customer records', ok: false },
    ],
    ok: false, verdict: 'Stopped', title: 'Stopped before it left your environment.',
    reason: 'This request appears to contain personal or sensitive data that your organization’s policy does not allow to be sent.',
    why: 'Personal data, model not approved for it',
  },
  {
    tab: 'Everyday request', who: 'Support agent', via: 'Using the company writing assistant',
    pre: 'Make this reply friendlier: “Your claim is in review and we will update you by Friday.”', hot: '', post: '',
    checks: [
      { label: 'Who is asking', finding: 'Support agent, signed in', ok: true },
      { label: 'What it contains', finding: 'Nothing sensitive', ok: true },
      { label: 'Where it is going', finding: 'A model you approved', ok: true },
    ],
    ok: true, verdict: 'Allowed', title: 'Sent to an approved model.',
    reason: 'Nothing sensitive was found and the destination is on your approved list. Work carries on without interruption.',
    why: 'Nothing sensitive, approved model',
  },
  {
    tab: 'AI agent reaches for a tool', who: 'Claims-processing agent', via: 'An AI agent working on its own',
    pre: 'Next action: send the customer file to an outside address using ', hot: 'a file-sharing tool', post: '.',
    checks: [
      { label: 'Who is asking', finding: 'Claims-processing agent, registered', ok: true },
      { label: 'What it wants to do', finding: 'Send a file outside the company', ok: false },
      { label: 'Which tool', finding: 'Not on this agent’s approved list', ok: false },
    ],
    ok: false, verdict: 'Stopped', title: 'Stopped before the tool was used.',
    reason: 'This agent may only use the tools your team approved. The tool it reached for is not on the list.',
    why: 'Tool not on the approved list',
  },
];

const FINISHED = 100000;
const two = (n: number) => String(n).padStart(2, '0');
const labelStyle = { margin: 0, fontFamily: 'var(--mono)', fontSize: 12, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--ink-3)' } as const;

/** Scripted sample: nothing here talks to a live system. */
export default function PolicySimulator() {
  const [sel, setSel] = useState(0);
  const [stage, setStage] = useState(0);
  const [typed, setTyped] = useState(FINISHED);
  const [log, setLog] = useState<LogRow[]>([]);
  const timers = useRef<number[]>([]);
  const ticker = useRef<number | null>(null);
  const count = useRef(0);
  const reduced = useRef(false);

  const clearRun = useCallback(() => {
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
    if (ticker.current !== null) { window.clearInterval(ticker.current); ticker.current = null; }
  }, []);

  const finish = useCallback((i: number) => {
    const s = SCENARIOS[i];
    const d = new Date();
    count.current += 1;
    const row: LogRow = {
      key: count.current,
      time: `${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`,
      who: s.who, decision: s.verdict, why: s.why, id: `Sample ${String(count.current).padStart(4, '0')}`, ok: s.ok,
    };
    setStage(4);
    setTyped(FINISHED);
    setLog(prev => [row, ...prev].slice(0, 4));
  }, []);

  const run = useCallback((i: number) => {
    clearRun();
    const s = SCENARIOS[i];
    const total = (s.pre + s.hot + s.post).length;
    if (reduced.current) { setSel(i); setStage(0); setTyped(FINISHED); finish(i); return; }
    setSel(i); setStage(0); setTyped(0);
    let n = 0;
    ticker.current = window.setInterval(() => {
      n += 3;
      if (n >= total) {
        if (ticker.current !== null) { window.clearInterval(ticker.current); ticker.current = null; }
        setTyped(FINISHED);
        ([[1, 350], [2, 1150], [3, 1950]] as const).forEach(([st, ms]) => timers.current.push(window.setTimeout(() => setStage(st), ms)));
        timers.current.push(window.setTimeout(() => finish(i), 2800));
      } else {
        setTyped(n);
      }
    }, 30);
  }, [clearRun, finish]);

  useEffect(() => {
    reduced.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const t = window.setTimeout(() => run(0), 1500);
    return () => { window.clearTimeout(t); clearRun(); };
  }, [run, clearRun]);

  const s = SCENARIOS[sel];
  const total = (s.pre + s.hot + s.post).length;
  const typing = typed < total;
  const done = stage >= 4;
  const verdictCls = done ? (s.ok ? ' ok' : ' stop') : '';
  const pre = s.pre.slice(0, typed);
  const hot = s.hot.slice(0, Math.max(0, typed - s.pre.length));
  const post = s.post.slice(0, Math.max(0, typed - s.pre.length - s.hot.length));

  return (
    <div className="frame2" style={{ background: 'rgba(255,255,255,0.55)', borderColor: 'rgba(255,255,255,0.9)', boxShadow: '0 30px 60px -30px rgba(28,27,24,0.22)' }}>
      <div className="frame2-in" style={{ position: 'relative' }}>
        <div style={{ padding: 28, display: 'flex', flexWrap: 'wrap', gap: '20px 40px', alignItems: 'flex-end', justifyContent: 'space-between', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
            <p style={labelStyle}>Interactive sample · simulated, not a live system</p>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 500, letterSpacing: '-0.02em', lineHeight: 1.2 }}>Send a request and watch what happens to it.</h2>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {SCENARIOS.map((x, i) => (
              <button key={x.tab} type="button" className={`tab${i === sel ? ' sel' : ''}`} aria-pressed={i === sel} onClick={() => run(i)}
                style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink)', background: '#fff', border: '1px solid var(--line-2)', borderRadius: 999, padding: '0 16px', minHeight: 44, cursor: 'pointer' }}>
                {x.tab}
              </button>
            ))}
          </div>
        </div>

        <div aria-hidden="true" style={{ padding: '16px 28px 14px', borderBottom: '1px solid var(--line)', background: '#fcfcfb', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>
            <span>Your people and agents</span><span style={{ textAlign: 'right' }}>AI models and tools</span>
          </div>
          <div style={{ position: 'relative', height: 26 }}>
            <div style={{ position: 'absolute', left: 0, right: 0, top: 12, height: 1, background: 'var(--line-2)' }} />
            <div className={`trail s${stage}${verdictCls}`} style={{ position: 'absolute', left: 0, top: 12, height: 1 }} />
            <div className={`gate${verdictCls}`} style={{ position: 'absolute', left: '62%', top: '50%', width: 2, borderRadius: 2, transform: 'translate(-50%, -50%)' }} />
            <div className={`pk s${stage}${verdictCls}`} style={{ position: 'absolute', top: 13, width: 10, height: 10, margin: '-5px 0 0 -5px', borderRadius: 999 }} />
          </div>
          <div style={{ position: 'relative', height: 14, fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>
            <span style={{ position: 'absolute', left: '62%', top: 0, transform: 'translateX(-50%)', whiteSpace: 'nowrap' }}>Your rules</span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))', gap: 1, background: 'var(--line)' }}>
          <div style={{ background: '#fff', padding: 28, display: 'flex', flexDirection: 'column', gap: 18 }}>
            <p style={labelStyle}>1 · The request</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 16, fontWeight: 500 }}>{s.who}</span>
              <span style={{ fontSize: 14, color: 'var(--ink-3)' }}>{s.via}</span>
            </div>
            <p className={`msg${stage === 1 || stage === 2 ? ' scan' : ''}`} style={{ margin: 0, padding: '16px 18px', background: 'var(--panel-2)', border: '1px solid var(--line)', borderRadius: 12, fontSize: 16, lineHeight: 1.6, minHeight: 132 }}>
              {pre}<span className={`hot${s.hot && stage >= 2 ? ' lit' : ''}`}>{hot}</span>{post}
              {typing && <span className="caret" aria-hidden="true" />}
            </p>
            <button type="button" className="btn-s" onClick={() => run(sel)} style={{ alignSelf: 'flex-start', gap: 8, fontSize: 15, padding: '0 18px', minHeight: 44 }}>
              <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8h10M9 4l4 4-4 4" /></svg>
              <span>{done ? 'Send it again' : 'Send this request'}</span>
            </button>
          </div>

          <div style={{ background: '#fff', padding: 28, display: 'flex', flexDirection: 'column', gap: 18 }}>
            <p style={labelStyle}>2 · Checked against your rules</p>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {s.checks.map((c, i) => (
                <div key={c.label} className={`chk${stage >= i + 1 ? ' on' : ''}`} style={{ display: 'flex', gap: 14, alignItems: 'flex-start', padding: '16px 0', borderBottom: '1px solid var(--line)' }}>
                  <span aria-hidden="true" style={{ flex: 'none', width: 26, height: 26, borderRadius: 999, border: '1px solid var(--line-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)' }}>{i + 1}</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                    <span style={{ fontSize: 14, color: 'var(--ink-3)' }}>{c.label}</span>
                    <span className="find" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16, fontWeight: 500 }}>
                      {c.ok
                        ? <svg role="img" aria-label="Passed" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="var(--ok)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flex: 'none' }}><path d="M3.5 8.5l3 3 6-7" /></svg>
                        : <svg role="img" aria-label="Not allowed" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="var(--stop)" strokeWidth="1.8" strokeLinecap="round" style={{ flex: 'none' }}><circle cx="8" cy="8" r="6" /><path d="M4 12L12 4" /></svg>}
                      <span>{c.finding}</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ background: '#fff', padding: 28, display: 'flex', flexDirection: 'column', gap: 18 }}>
            <p style={labelStyle}>3 · The decision</p>
            <div className={`out ${s.ok ? 'ok' : 'stop'}${done ? ' on' : ''}`} aria-live="polite" style={{ border: '1px solid var(--line)', borderRadius: 12, padding: 20, display: 'flex', flexDirection: 'column', gap: 12, minHeight: 196 }}>
              <span className="verdict" style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" style={{ flex: 'none' }}>
                  {s.ok ? <circle cx="7" cy="7" r="5" fill="var(--ok)" /> : <rect x="2" y="2" width="10" height="10" rx="2" fill="var(--stop)" />}
                </svg>
                <span>{s.verdict}</span>
              </span>
              <span style={{ fontSize: 20, fontWeight: 500, letterSpacing: '-0.015em', lineHeight: 1.25 }}>{s.title}</span>
              <span style={{ fontSize: 15, lineHeight: 1.55, color: 'var(--ink-2)' }}>{s.reason}</span>
            </div>
            <p style={{ margin: 0, fontSize: 14, color: 'var(--ink-3)' }}>The person or agent is told why, in plain words, at the moment it happens.</p>
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--line)', padding: '24px 28px 28px', display: 'flex', flexDirection: 'column', gap: 14, background: '#fcfcfb' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 24px', alignItems: 'baseline', justifyContent: 'space-between' }}>
            <p style={labelStyle}>4 · Recorded for your auditors</p>
            <p style={{ margin: 0, fontSize: 14, color: 'var(--ink-3)' }}>Every decision adds a line. Try another request and watch the record grow.</p>
          </div>
          {log.length === 0 && <p style={{ margin: 0, padding: '14px 0', borderTop: '1px solid var(--line)', fontSize: 15, color: 'var(--ink-3)' }}>Nothing recorded yet. Send a request above.</p>}
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {log.map(r => (
              <div key={r.key} className={`logrow ${r.ok ? 'ok' : 'stop'}`} style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 24px', alignItems: 'baseline', padding: '12px 0', borderTop: '1px solid var(--line)', fontFamily: 'var(--mono)', fontSize: 13, lineHeight: 1.5 }}>
                <span style={{ color: 'var(--ink-3)', flex: '0 0 76px' }}>{r.time}</span>
                <span style={{ flex: '0 0 200px', color: 'var(--ink)' }}>{r.who}</span>
                <span className="dec" style={{ flex: '0 0 84px', fontWeight: 500 }}>{r.decision}</span>
                <span style={{ flex: '1 1 260px', color: 'var(--ink-2)', minWidth: 0 }}>{r.why}</span>
                <span style={{ color: 'var(--ink-3)' }}>{r.id}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
