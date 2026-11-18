import { useEffect, useRef, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';

function setSpot(e: MouseEvent<HTMLElement>) {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`);
}

const pillOk = { fontSize: 13, fontWeight: 500, color: 'var(--ok)', background: 'var(--ok-bg)', borderRadius: 999, padding: '5px 12px' } as const;
const row = { display: 'flex', flexWrap: 'wrap', gap: '6px 16px', justifyContent: 'space-between', alignItems: 'center', padding: '16px 22px', borderBottom: '1px solid var(--line)' } as const;
const tool = { display: 'flex', gap: 16, justifyContent: 'space-between', alignItems: 'center', padding: '15px 22px', borderBottom: '1px solid var(--line)' } as const;
const detail = { display: 'flex', flexWrap: 'wrap', gap: '4px 20px', padding: '14px 22px', borderBottom: '1px solid var(--line)' } as const;

function Approved() {
  return <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: 'var(--ok)', whiteSpace: 'nowrap' }}><svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3.5 8.5l3 3 6-7" /></svg>Approved</span>;
}
function NotApproved() {
  return <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: 'var(--stop)', whiteSpace: 'nowrap' }}><svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="8" cy="8" r="6" /><path d="M4 12L12 4" /></svg>Not approved</span>;
}
function Detail({ k, children, last, mono }: { k: string; children: ReactNode; last?: boolean; mono?: boolean }) {
  return (
    <div style={{ ...detail, borderBottom: last ? 0 : detail.borderBottom }}>
      <span style={{ flex: '0 0 150px', fontSize: 14, color: 'var(--ink-3)' }}>{k}</span>
      <span style={{ flex: '1 1 220px', minWidth: 0, fontSize: mono ? 13 : 15, fontFamily: mono ? 'var(--mono)' : undefined }}>{children}</span>
    </div>
  );
}
function Panel({ children }: { children: ReactNode }) {
  return (
    <div className="spot frame2" onMouseMove={setSpot}>
      <div className="frame2-in">{children}</div>
    </div>
  );
}

const LABELS = ['Sensitive data', 'AI agents', 'The audit record'];

export default function ControlsStory() {
  const [active, setActive] = useState(0);
  const refs = useRef<Array<HTMLElement | null>>([]);

  useEffect(() => {
    if (!('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver(entries => {
      entries.forEach(en => {
        if (!en.isIntersecting) return;
        const i = refs.current.indexOf(en.target as HTMLElement);
        if (i >= 0) setActive(i);
      });
    }, { rootMargin: '-45% 0px -45% 0px' });
    refs.current.forEach(el => el && io.observe(el));
    return () => io.disconnect();
  }, []);

  const go = (i: number) => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    refs.current[i]?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    setActive(i);
  };

  const heading = (n: string, title: string, body: string) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <p className="mono" style={{ margin: 0, fontSize: 13, color: 'var(--ink-3)' }}>{n}</p>
      <h3 style={{ margin: 0, fontSize: 'clamp(26px, 2.6vw, 36px)', lineHeight: 1.12, fontWeight: 500, letterSpacing: '-0.025em' }}>{title}</h3>
      <p style={{ margin: 0, color: 'var(--ink-2)', textWrap: 'pretty' }}>{body}</p>
    </div>
  );
  const article = { display: 'flex', flexDirection: 'column', gap: 28 } as const;

  return (
    <section id="controls" style={{ padding: '0 24px', background: '#fff', scrollMarginTop: 110 }} aria-labelledby="controls-title">
      <div className="rail" style={{ maxWidth: 1240, margin: '0 auto', padding: '112px clamp(20px, 4vw, 56px)', display: 'flex', flexWrap: 'wrap', gap: '56px 88px', alignItems: 'flex-start' }}>
        <div className="story-left" style={{ flex: '1 1 340px', minWidth: 0, position: 'sticky', top: 130, display: 'flex', flexDirection: 'column', gap: 36 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <p className="eyebrow">What it controls</p>
            <h2 id="controls-title" style={{ margin: 0, fontSize: 'clamp(30px, 3.2vw, 44px)', lineHeight: 1.08, fontWeight: 500, letterSpacing: '-0.032em', textWrap: 'balance' }}>One checkpoint between your people and every AI model and tool they use.</h2>
          </div>
          <div className="story-idx" style={{ display: 'flex', flexDirection: 'column' }}>
            {LABELS.map((label, i) => (
              <button key={label} type="button" className={`idx${i === active ? ' on' : ''}`} aria-pressed={i === active} onClick={() => go(i)}
                style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 16, textAlign: 'left', background: 'none', border: 0, borderTop: '1px solid var(--line)', padding: '0 2px', minHeight: 56, fontSize: 18, fontWeight: 500, letterSpacing: '-0.015em', cursor: 'pointer', color: 'inherit', fontFamily: 'inherit' }}>
                <span className="bar" aria-hidden="true" style={{ position: 'absolute', top: -1, left: 0, right: 0, height: 1, background: 'var(--ink)' }} />
                <span className="mono" style={{ fontSize: 13, fontWeight: 400 }}>0{i + 1}</span>
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: '1.45 1 480px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 112 }}>
          <article ref={el => { refs.current[0] = el; }} style={article}>
            {heading('01', 'Sensitive data stays where it belongs.', 'You decide which kinds of information may reach which AI models. Customer records can be limited to a model you run yourself. Anything headed somewhere you have not approved is stopped, or has the sensitive details removed, before it leaves.')}
            <Panel>
              <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--line)', fontSize: 15, fontWeight: 500 }}>Where each kind of information may go</div>
              <div style={row}><span style={{ fontSize: 15 }}>Customer records</span><span style={pillOk}>Your own model only</span></div>
              <div style={row}><span style={{ fontSize: 15 }}>Internal documents</span><span style={pillOk}>Approved models</span></div>
              <div style={row}><span style={{ fontSize: 15 }}>Public information</span><span style={pillOk}>Approved models</span></div>
              <div style={{ ...row, borderBottom: 0 }}><span style={{ fontSize: 15 }}>Anything, to a model not on your list</span><span style={{ ...pillOk, color: 'var(--stop)', background: 'var(--stop-bg)' }}>Stopped</span></div>
            </Panel>
          </article>

          <article ref={el => { refs.current[1] = el; }} style={article}>
            {heading('02', 'AI agents stay on approved tools.', 'An AI agent can act as well as answer: read a file, send a message, change a record. You approve the short list of things each agent may do. If it reaches for anything else, the action is stopped before it happens.')}
            <Panel>
              <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 15, fontWeight: 500 }}>Claims-processing agent</span>
                <span style={{ fontSize: 13, color: 'var(--ink-3)' }}>What this agent may do</span>
              </div>
              {['Read claim files', 'Look up policy wording', 'Draft a letter for a person to review'].map(t => (
                <div key={t} style={tool}><span style={{ fontSize: 15 }}>{t}</span><Approved /></div>
              ))}
              <div style={{ ...tool, background: '#fdf8f6' }}><span style={{ fontSize: 15 }}>Send files outside the company</span><NotApproved /></div>
              <div style={{ ...tool, background: '#fdf8f6', borderBottom: 0 }}><span style={{ fontSize: 15 }}>Delete records</span><NotApproved /></div>
            </Panel>
          </article>

          <article ref={el => { refs.current[2] = el; }} style={article}>
            {heading('03', 'Everything is provable to auditors.', 'Each decision is written down as it is made: who asked, what was found, which rule applied, and what happened next. When an auditor asks how you know, you open the record and export it.')}
            <Panel>
              <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--line)', display: 'flex', flexWrap: 'wrap', gap: '8px 16px', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 15, fontWeight: 500 }}>One record, opened (sample)</span>
                <span style={{ fontSize: 13, fontWeight: 500, border: '1px solid var(--line-2)', borderRadius: 999, padding: '5px 12px' }}>Export for auditors</span>
              </div>
              <Detail k="Decision"><span style={{ fontWeight: 500, color: 'var(--stop)' }}>Stopped</span></Detail>
              <Detail k="Who asked">Claims analyst, using the chat assistant</Detail>
              <Detail k="What was found">Confidential: a Social Security number</Detail>
              <Detail k="They were told">This request appears to contain personal or sensitive data that your organization’s policy does not allow to be sent.</Detail>
              <Detail k="Reached the AI model">No</Detail>
              <Detail k="Record number" last mono>Sample record 0001</Detail>
            </Panel>
          </article>
        </div>
      </div>
    </section>
  );
}
