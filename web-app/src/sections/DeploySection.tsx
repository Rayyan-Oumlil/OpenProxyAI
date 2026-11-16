import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';
import { GITHUB_URL, docsPage } from '../lib/links';

const POINTS = [
  { title: 'Read it', text: 'Apache-2.0, in one public repository. Every claim on this site points at a file, a test or a docs page you can check.' },
  { title: 'Run it where your data lives', text: 'Docker Compose, a Helm chart and an air-gap mode. It runs against your own Postgres and Redis, with your provider keys.' },
  { title: 'Isolate each org in the database', text: 'Postgres row-level security scopes every query to one organization, not only the application code.' },
];

const REQUEST = `curl https://gateway.your-company.com/v1/chat/completions \\
  -H "Authorization: Bearer $OPENPROXY_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}'`;

export default function DeploySection() {
  return (
    <Section id="deploy" label="§07 · host it, verify it" title={<>You host it. <em>So you can read it.</em></>} aside="self-hosted">
      <div className="split">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {POINTS.map(p => (
            <div key={p.title} style={{ borderLeft: '2px solid var(--accent)', paddingLeft: 16 }}>
              <div style={{ color: 'var(--ink)', fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{p.title}</div>
              <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)' }}>{p.text}</p>
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <a className="opa-btn" href={docsPage('/guides/deployment')} target="_blank" rel="noopener noreferrer">$ deployment guide →</a>
            <a className="opa-btn" href={GITHUB_URL} target="_blank" rel="noopener noreferrer" data-track="cta_github">$ view on github</a>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
          <CodeBlock title="after you deploy · first call" copy={REQUEST}>
            <span className="tok-dim">$ </span>{REQUEST}
          </CodeBlock>
          <CodeBlock title="response headers you get back" tag="captured output">
            <span className="tok-dim">x-openproxyai-request-id: </span>{'<id to open in the request trace>\n'}
            <span className="tok-dim">x-openproxyai-provider: </span>{'openai\n'}
            <span className="tok-dim">x-openproxyai-data-class: </span>{'internal\n'}
            <span className="tok-dim">x-openproxyai-cache: </span>{'miss'}
          </CodeBlock>
        </div>
      </div>
    </Section>
  );
}
