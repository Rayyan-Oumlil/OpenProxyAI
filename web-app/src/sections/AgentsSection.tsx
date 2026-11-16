import Section from '../components/Section';
import { docsPage } from '../lib/links';

const CONTROLS = [
  { title: 'Approve the tools', text: 'AI agents can only use business tools you connected and approved. Group them into sets per team or application, and every tool call is recorded.' },
  { title: 'Lock the definitions', text: 'If a tool’s instructions change after you approved it, the tool is blocked until someone reviews the change. No silent surprises.' },
  { title: 'Contain the risk', text: 'Content coming back from an untrusted tool cannot trigger sensitive actions. Your people’s credentials are never handed to a tool.' },
];

export default function AgentsSection() {
  return (
    <Section id="agents" label="AI agents" title={<>Agents act on your behalf. <em>Keep them on a short leash.</em></>} aside="tools your agents can reach">
      <div className="grid-3">
        {CONTROLS.map(c => (
          <div key={c.title} className="opa-card" style={{ padding: 22 }}>
            <h3 style={{ margin: '0 0 8px', color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{c.title}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 15, lineHeight: 1.6, color: 'var(--ink-2)' }}>{c.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        Built on the open Model Context Protocol (MCP), the standard way AI agents connect to tools.{' '}
        <a href={docsPage('/guides/mcp-gateway')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Read the guide →</a>
      </p>
    </Section>
  );
}
