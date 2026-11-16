import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';
import { docsPage, repoFile } from '../lib/links';

const CONTROLS = [
  {
    title: 'Tool pinning',
    text: 'The gateway stores a hash of each tool definition and serves only what an admin approved. If a server edits a description later, the tool is refused until someone reviews it.',
  },
  {
    title: 'Taint tracking',
    text: 'A result from a tool you did not mark as trusted taints the session. A sink tool then refuses to run in that session, so injected text cannot trigger a dangerous action.',
  },
  {
    title: 'Credentials stay put',
    text: 'The agent’s key authenticates it to the gateway only. It is never forwarded to a tool server, and a regression test holds that line.',
    href: repoFile('backend/tests/test_mcp_token_isolation.py'),
    linkLabel: 'see the test',
  },
];

export default function McpSection() {
  return (
    <Section id="mcp" label="§05 · bound your agents" title={<>Agents get the tools you approved, <em>as you approved them.</em></>} aside="mcp gateway">
      <div className="split">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <p className="lede">
            One endpoint and one key for all your MCP tool servers. Every tool call is checked against policy and written to the audit log, like a model call.
          </p>
          {CONTROLS.map(c => (
            <div key={c.title} style={{ borderLeft: '2px solid var(--accent)', paddingLeft: 16 }}>
              <div style={{ color: 'var(--ink)', fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{c.title}</div>
              <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)' }}>
                {c.text}{' '}
                {c.href && <a href={c.href} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>{c.linkLabel} →</a>}
              </p>
            </div>
          ))}
          <a className="opa-btn" style={{ alignSelf: 'flex-start' }} href={docsPage('/guides/mcp-gateway')} target="_blank" rel="noopener noreferrer">$ read the MCP guide →</a>
        </div>

        <CodeBlock title="pin_mode: enforce" tag="illustration">
          <span className="tok-dim">{'// 1. an admin approves the tool\n'}</span>
          <span className="tok-ok">✓</span>{' tools/list   github__search   '}<span className="tok-ok">approved</span>{'\n\n'}
          <span className="tok-dim">{'// 2. the server changes the tool description\n'}</span>
          <span className="tok-ok">◉</span>{' tools/list   github__search   '}<span className="tok-bad">drifted</span>{' (hash changed)\n\n'}
          <span className="tok-dim">{'// 3. an agent tries to call it anyway\n'}</span>
          {'tools/call   github__search\n'}
          <span className="tok-bad">error -32004</span>{'  tool not approved (drifted)\n\n'}
          <span className="tok-dim">{'// the gateway re-checks pinned servers every 15 minutes,\n// so drift is found even when no agent is calling.'}</span>
        </CodeBlock>
      </div>
    </Section>
  );
}
