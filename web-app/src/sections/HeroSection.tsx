import type { MouseEvent } from 'react';
import FlowDiagram from '../components/FlowDiagram';
import PolicySimulator from '../components/PolicySimulator';
import { CALENDLY_URL, GITHUB_URL } from '../lib/links';

const WORDS: Array<[string, boolean]> = [
  ['Sensitive', false], ['data', false], ['and', false], ['AI', false], ['agents,', false],
  ['under', true], ['your', true], ['control.', true],
];

function setSpot(e: MouseEvent<HTMLElement>) {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`);
}

export default function HeroSection() {
  return (
    <section onMouseMove={setSpot} style={{ position: 'relative', padding: '0 24px' }} aria-label="OpenProxyAI">
      <div className="dots" aria-hidden="true" style={{ position: 'absolute', top: 0, right: 0, width: '66%', height: 560, backgroundImage: 'radial-gradient(#c9d2d8 1px, transparent 1.4px)', backgroundSize: '22px 22px', WebkitMaskImage: 'radial-gradient(ellipse at 70% 30%, #000 0%, transparent 68%)', maskImage: 'radial-gradient(ellipse at 70% 30%, #000 0%, transparent 68%)', pointerEvents: 'none' }} />
      <div className="glowdots" aria-hidden="true" style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 620, backgroundImage: 'radial-gradient(#1c1b18 1.3px, transparent 1.7px)', backgroundSize: '22px 22px', pointerEvents: 'none', opacity: 0.55 }} />
      <div className="rail" style={{ maxWidth: 1240, margin: '0 auto', padding: '84px clamp(20px, 4vw, 56px) 96px', display: 'flex', flexDirection: 'column', gap: 72 }}>
        <div style={{ position: 'relative', display: 'flex', flexWrap: 'wrap', gap: '40px 72px', alignItems: 'flex-end' }}>
          <div style={{ flex: '1.5 1 520px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 28 }}>
            <p className="eyebrow rise" style={{ animationDelay: '.05s' }}>Runs in your own environment</p>
            <h1 style={{ margin: 0, fontSize: 'clamp(40px, 5.4vw, 72px)', lineHeight: 1.03, fontWeight: 500, letterSpacing: '-0.038em', textWrap: 'balance' }}>
              {WORDS.map(([w, soft], i) => (
                <span key={w}>
                  <span className="w" style={{ animationDelay: `${0.1 + i * 0.07 + (soft ? 0.05 : 0)}s`, color: soft ? 'var(--soft)' : undefined }}>{w}</span>{' '}
                </span>
              ))}
            </h1>
          </div>
          <div className="rise" style={{ flex: '1 1 360px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 28, animationDelay: '.75s' }}>
            <p style={{ margin: 0, fontSize: 18, lineHeight: 1.6, color: 'var(--ink-2)', textWrap: 'pretty' }}>
              For security and compliance teams. OpenProxyAI makes sure sensitive data only reaches the AI models you approved, and that AI agents only use the tools you approved. Every decision is recorded for your auditors.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              <a className="btn-p" href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" data-track="cta_book_demo" style={{ fontSize: 16, padding: '0 24px', minHeight: 48 }}>Book a demo</a>
              <a className="btn-s" href="#controls" data-track="cta_tour" style={{ fontSize: 16, padding: '0 24px', minHeight: 48 }}>See how it works</a>
            </div>
            <p style={{ margin: 0, fontSize: 14, color: 'var(--ink-3)' }}>Apache-2.0 open source, so you can read every line on <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" data-track="cta_github" style={{ textDecoration: 'underline', textUnderlineOffset: 3 }}>GitHub</a>. The gateway runs in your own cloud or data center.</p>
          </div>
        </div>

        <div className="rise" style={{ position: 'relative', borderRadius: 28, padding: 'clamp(10px, 3.2vw, 44px)', background: 'linear-gradient(180deg, #e2ecf1 0%, #eef4f7 70%, #f4f8fa 100%)', overflow: 'hidden', animationDelay: '.95s' }}>
          <div className="blob" aria-hidden="true" style={{ position: 'absolute', top: -160, left: -80, width: 520, height: 520, borderRadius: 999, background: '#cfdfe8', filter: 'blur(80px)', opacity: 0.9 }} />
          <div className="blob b2" aria-hidden="true" style={{ position: 'absolute', bottom: -220, right: -60, width: 560, height: 560, borderRadius: 999, background: '#ece8de', filter: 'blur(90px)', opacity: 0.9 }} />
          <div className="dots" aria-hidden="true" style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(#a9bcc7 1px, transparent 1.4px)', backgroundSize: '22px 22px', opacity: 0.55, WebkitMaskImage: 'linear-gradient(180deg, #000, transparent 55%)', maskImage: 'linear-gradient(180deg, #000, transparent 55%)' }} />

          <FlowDiagram />

          <PolicySimulator />
        </div>
      </div>
    </section>
  );
}
