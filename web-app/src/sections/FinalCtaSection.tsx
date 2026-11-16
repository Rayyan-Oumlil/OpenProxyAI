import { Link } from 'react-router-dom';
import CodeBlock from '../components/CodeBlock';
import { GITHUB_URL } from '../lib/links';

const DEMO_COMMAND = 'docker compose -f docker-compose.demo.yml up --build';

export default function FinalCtaSection() {
  return (
    <section className="sec" id="start" aria-labelledby="start-title" data-section="start">
      <div className="sec-wrap">
        <div
          className="split"
          style={{
            padding: 32, alignItems: 'center',
            border: '1px solid var(--accent)', borderRadius: 12,
            background: 'radial-gradient(ellipse 60% 100% at 90% 50%, color-mix(in srgb, var(--accent) 14%, transparent) 0%, transparent 70%), var(--panel)',
          }}
        >
          <div>
            <h2 id="start-title" className="sec-title">Run it. <em>Then read the code.</em></h2>
            <p className="lede" style={{ marginTop: 10 }}>
              The demo needs only Docker. It seeds an org, sends real traffic through the gateway and opens a console with the request trace, the policy and the audit log.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 18 }}>
              <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="opa-btn opa-btn-primary" data-track="cta_github">$ star it on github →</a>
              <Link to="/pricing" className="opa-btn">$ see plans</Link>
            </div>
          </div>
          <CodeBlock title="terminal · one command" copy={DEMO_COMMAND}>
            <span className="tok-dim">$ </span>{DEMO_COMMAND}
          </CodeBlock>
        </div>
      </div>
    </section>
  );
}
