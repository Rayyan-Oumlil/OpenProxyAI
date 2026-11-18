import type { MouseEvent } from 'react';

const STEPS = [
  { t: 'Someone asks.', d: 'A person, one of your apps, or an AI agent sends a request to an AI model or tries to use a tool.', icon: 'M3 4.5h10v6.5H7.5L5 13.5V11H3z' },
  { t: 'Your rules are checked.', d: 'Who is asking, what the request contains, and where it is headed are compared with the rules you set.', icon: 'M3 5l1.5 1.5L7 4M9.5 5H13M3 11l1.5 1.5L7 10M9.5 11H13' },
  { t: 'A decision is made.', d: 'The request is allowed, has its sensitive details removed, or is stopped. The person is told why.', icon: 'M8 2.5l5 2V8c0 3-2.2 4.8-5 5.5C5.2 12.8 3 11 3 8V4.5zM6 8l1.5 1.5L10 6.5' },
  { t: 'It is written down.', d: 'The decision and the reason go into a record you can search, review and hand to an auditor.', icon: 'M3.5 2.5h9v11h-9zM6 6h4M6 8.5h4M6 11h2.5' },
];

function setSpot(e: MouseEvent<HTMLElement>) {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`);
}

const node = { flex: '1 1 150px', display: 'flex', alignItems: 'center', gap: 10, padding: '13px 14px', background: '#fff', border: '1px solid var(--line-2)', borderRadius: 12, fontSize: 14, fontWeight: 500 } as const;
const arrow = (c: string) => <svg width="20" height="20" viewBox="0 0 16 16" fill="none" stroke={c} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" style={{ flex: 'none' }} aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4" /></svg>;

export default function HowItWorksSection() {
  return (
    <section id="how" aria-labelledby="how-title" style={{ padding: '0 24px', borderTop: '1px solid var(--line)', background: 'var(--bg-2)', scrollMarginTop: 110 }}>
      <div className="rail" style={{ maxWidth: 1240, margin: '0 auto', padding: '112px clamp(20px, 4vw, 56px)', display: 'flex', flexDirection: 'column', gap: 64 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 820 }}>
          <p className="eyebrow">How it works</p>
          <h2 id="how-title" style={{ margin: 0, fontSize: 'clamp(32px, 3.8vw, 52px)', lineHeight: 1.06, fontWeight: 500, letterSpacing: '-0.032em', textWrap: 'balance' }}>The same four steps, every time, for every request.</h2>
        </div>
        <ol data-how="steps" style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(230px, 100%), 1fr))', gap: '40px 0' }}>
          {STEPS.map((s, i) => (
            <li key={s.t} style={{ position: 'relative', borderTop: '1px solid var(--line-2)', padding: '20px 28px 0 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <span className="draw" aria-hidden="true" style={{ position: 'absolute', top: -1, left: 0, right: 0, height: 1, background: 'var(--ink)', transformOrigin: 'left' }} />
              <span className="how-icon" aria-hidden="true" style={{ width: 48, height: 48, marginBottom: 8, border: '1px solid var(--line-2)', borderRadius: 14, background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="22" height="22" viewBox="0 0 16 16" fill="none" stroke="var(--ink)" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><path d={s.icon} /></svg>
              </span>
              <span className="mono" style={{ fontSize: 13, color: 'var(--ink-3)' }}>Step {i + 1}</span>
              <span style={{ fontSize: 20, fontWeight: 500, letterSpacing: '-0.015em' }}>{s.t}</span>
              <span style={{ fontSize: 16, color: 'var(--ink-2)' }}>{s.d}</span>
            </li>
          ))}
        </ol>
        <div className="spot frame2" onMouseMove={setSpot}>
          <div className="frame2-in" style={{ padding: 'clamp(28px, 4vw, 56px)', display: 'flex', flexWrap: 'wrap', gap: '24px 72px', alignItems: 'center' }}>
            <h3 style={{ flex: '1 1 340px', minWidth: 0, margin: 0, fontSize: 'clamp(26px, 2.8vw, 38px)', lineHeight: 1.1, fontWeight: 500, letterSpacing: '-0.028em', textWrap: 'balance' }}>It runs inside your own environment.</h3>
            <p style={{ flex: '1.2 1 380px', minWidth: 0, margin: 0, color: 'var(--ink-2)', textWrap: 'pretty' }}>OpenProxyAI is installed where your systems already live, under your own security controls. Your requests and your records stay with you. They do not pass through us.</p>
            <div role="img" aria-label="Inside your environment: people and agents, OpenProxyAI, and the audit record. Only approved requests leave, to approved AI models and tools." style={{ flex: '1 1 100%', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 14 }}>
              <div style={{ position: 'relative', flex: '3 1 420px', minWidth: 0, border: '1.5px dashed #aaa79d', borderRadius: 18, background: 'var(--panel-2)', padding: '40px 18px 18px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
                <span style={{ position: 'absolute', top: 12, left: 18, fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>Your environment</span>
                <span style={node}>People, apps and agents</span>
                {arrow('#8b887f')}
                <span style={{ ...node, borderColor: 'var(--ink)' }}>OpenProxyAI</span>
                {arrow('#8b887f')}
                <span style={node}>The audit record</span>
              </div>
              {arrow('#1c1b18')}
              <span style={{ ...node, flex: '1 1 200px', background: 'var(--ok-bg)', borderColor: 'var(--ok-line)' }}>Approved AI models and tools</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
