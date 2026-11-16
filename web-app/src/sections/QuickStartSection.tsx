import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';
import { docsPage, repoFile } from '../lib/links';

const DEMO_COMMAND = 'docker compose -f docker-compose.demo.yml up --build';

export default function QuickStartSection() {
  return (
    <Section id="try" label="For your engineers" title={<>They can try it <em>in minutes.</em></>} aside="no provider key needed">
      <div className="split">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p className="lede">
            OpenProxyAI works with any tool or application that can call an OpenAI-compatible service. Your engineers change one address and one key, and nothing else in their code. A local demo with sample traffic runs on a laptop with Docker.
          </p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <a className="opa-btn" href={docsPage('/getting-started/quickstart')} target="_blank" rel="noopener noreferrer">Quickstart</a>
            <a className="opa-btn" href={repoFile('README.md')} target="_blank" rel="noopener noreferrer">README and demo login</a>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
          <CodeBlock title="terminal · local demo" copy={DEMO_COMMAND}>
            <span className="tok-dim">$ </span>{DEMO_COMMAND}
          </CodeBlock>
          <CodeBlock title="your application · what changes" tag="python">
            {'client = OpenAI(\n'}
            <span className="diff-del">{'-   base_url="https://api.openai.com/v1",\n'}</span>
            <span className="diff-add">{'+   base_url="https://gateway.your-company.com/v1",\n'}</span>
            {')'}
          </CodeBlock>
        </div>
      </div>
    </Section>
  );
}
