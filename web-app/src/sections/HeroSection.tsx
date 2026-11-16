import CodeBlock from '../components/CodeBlock';
import { GITHUB_URL } from '../lib/links';

const DEMO_COMMAND = 'docker compose -f docker-compose.demo.yml up --build';

export default function HeroSection() {
  return (
    <div className="sec-wrap" style={{ padding: '28px 24px 40px' }}>
      <div className="split" style={{ gridTemplateColumns: 'minmax(0,1.15fr) minmax(0,1fr)', gap: 20 }}>
        <div
          style={{
            padding: '28px 24px 24px',
            display: 'flex', flexDirection: 'column', gap: 16,
            border: '1px solid var(--line)', borderRadius: 10,
            background: 'radial-gradient(ellipse 80% 100% at 80% 0%, color-mix(in srgb, var(--accent) 10%, transparent) 0%, transparent 60%), var(--panel)',
          }}
        >
          <span style={{ fontSize: 11, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>
            Open source · Apache-2.0 · self-hosted
          </span>
          <h1 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(32px,3.6vw,52px)', lineHeight: 1.04, letterSpacing: '-0.03em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            The LLM gateway for teams that must <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>prove</em> what their AI did.
          </h1>
          <p className="lede">
            OpenAI-compatible: change the <code>base_url</code>, keep your SDK. Every request is policy-checked, routed by data class and written to an audit trail. You host it, so you can read it.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
            <a href="#try" className="opa-btn opa-btn-primary" data-track="cta_run_demo">$ run the demo →</a>
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="opa-btn" data-track="cta_github">$ view on github</a>
          </div>
          <p className="note" style={{ margin: 0 }}>Needs Docker. No provider key, no signup, no cost.</p>
        </div>

        <div id="try" style={{ display: 'flex', flexDirection: 'column', gap: 14, scrollMarginTop: 76, minWidth: 0 }}>
          <CodeBlock title="terminal · one command" copy={DEMO_COMMAND}>
            <span className="tok-dim">$ </span>{DEMO_COMMAND}{'\n'}
            <span className="tok-dim"># console at http://localhost:5173, API at http://localhost:8000</span>{'\n'}
            <span className="tok-dim"># needs ports 8000 and 5173 free; the model is a fake local server</span>
          </CodeBlock>
          <CodeBlock title="your code · what changes" tag="python">
            {'client = OpenAI(\n'}
            <span className="diff-del">{'-   base_url="https://api.openai.com/v1",\n'}</span>
            <span className="diff-add">{'+   base_url="https://gateway.your-company.com/v1",\n'}</span>
            <span className="diff-del">{'-   api_key=OPENAI_API_KEY,\n'}</span>
            <span className="diff-add">{'+   api_key=OPENPROXY_KEY,\n'}</span>
            {')'}
          </CodeBlock>
        </div>
      </div>
    </div>
  );
}
