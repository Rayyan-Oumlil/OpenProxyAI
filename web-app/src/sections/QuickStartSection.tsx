import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';
import { repoFile } from '../lib/links';

const DEMO_COMMAND = 'docker compose -f docker-compose.demo.yml up --build';

const STEPS = [
  { n: '1', title: 'Run the demo', text: 'One command starts the gateway, Postgres, Redis, a fake model server and the console, then sends sample traffic. No provider key and no cost.' },
  { n: '2', title: 'Open the console', text: 'Go to localhost:5173 and sign in with the public demo login in the README. Open a request trace, send a prompt with an SSN and watch policy refuse it.' },
  { n: '3', title: 'Point your SDK at it', text: 'In your own deployment, change the base_url and the key. Nothing else in your code changes.' },
];

export default function QuickStartSection() {
  return (
    <Section id="try" label="§02 · try it" title={<>From clone to a refused request <em>in minutes.</em></>} aside="needs only docker">
      <div className="grid-3" style={{ marginBottom: 22 }}>
        {STEPS.map(s => (
          <div key={s.n} className="opa-card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <span style={{ width: 24, height: 24, borderRadius: '50%', border: '1px solid var(--accent)', color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>{s.n}</span>
              <span style={{ color: 'var(--ink)', fontSize: 14, fontWeight: 500 }}>{s.title}</span>
            </div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)' }}>{s.text}</p>
          </div>
        ))}
      </div>
      <div className="grid-2">
        <CodeBlock title="terminal · one command" copy={DEMO_COMMAND}>
          <span className="tok-dim">$ </span>{DEMO_COMMAND}{'\n'}
          <span className="tok-dim"># console at http://localhost:5173, API at http://localhost:8000{'\n'}# needs ports 8000 and 5173 free; the model is a fake local server</span>
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
      <p className="note">
        The demo login and the full walkthrough are in the{' '}
        <a href={repoFile('README.md')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>README →</a>
      </p>
    </Section>
  );
}
