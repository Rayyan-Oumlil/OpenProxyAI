import HeroDiagram from '../components/HeroDiagram';
import { CALENDLY_URL } from '../lib/links';

export default function HeroSection() {
  return (
    <div className="sec-wrap" style={{ padding: '44px 24px 52px' }}>
      <div className="split hero-split">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '8px 4px' }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Open source · Runs in your own environment
          </span>
          <h1 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(36px,4.2vw,60px)', lineHeight: 1.05, letterSpacing: '-0.03em', fontWeight: 600, margin: 0, color: 'var(--ink)' }}>
            Let your teams use AI. <span style={{ color: 'var(--accent)' }}>Stay in control</span> of what it does.
          </h1>
          <p className="lede" style={{ fontSize: 17, maxWidth: '54ch' }}>
            OpenProxyAI sits between your people, your applications and the AI models they use. It enforces your rules, keeps sensitive data where it belongs, controls cost, and records everything for your auditors.
          </p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <a href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" className="opa-btn opa-btn-primary" data-track="cta_book_demo">Book a demo</a>
            <a href="#tour" className="opa-btn" data-track="cta_tour">See how it works</a>
          </div>
          <p className="note" style={{ margin: 0 }}>Apache-2.0 open source. The gateway runs in your own cloud or data center.</p>
        </div>
        <HeroDiagram />
      </div>
    </div>
  );
}
