import HeroDiagram from '../components/HeroDiagram';
import { GITHUB_URL } from '../lib/links';

export default function HeroSection() {
  return (
    <div className="sec-wrap" style={{ padding: '28px 24px 40px' }}>
      <div className="split hero-split">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18, padding: '12px 4px' }}>
          <span style={{ fontSize: 11, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>
            Open source · Apache-2.0 · self-hosted
          </span>
          <h1 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(34px,4vw,58px)', lineHeight: 1.03, letterSpacing: '-0.03em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            The LLM gateway for teams that must <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>prove</em> what their AI did.
          </h1>
          <p className="lede">
            OpenAI-compatible: change the <code>base_url</code>, keep your SDK. Every request is policy-checked, routed by data class and written to an audit trail. You host it, so you can read it.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <a href="#try" className="opa-btn opa-btn-primary" data-track="cta_run_demo">$ run the demo →</a>
            <a href="#tour" className="opa-btn" data-track="cta_tour">$ see the console</a>
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="opa-btn" data-track="cta_github">$ github</a>
          </div>
          <p className="note" style={{ margin: 0 }}>Needs Docker. No provider key, no signup, no cost.</p>
        </div>
        <HeroDiagram />
      </div>
    </div>
  );
}
