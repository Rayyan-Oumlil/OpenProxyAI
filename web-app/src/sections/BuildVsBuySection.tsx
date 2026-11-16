import Section from '../components/Section';
import { docsPage } from '../lib/links';

const ROWS = [
  { item: 'Multi-provider routing and failover', build: 'Provider quirks, key rotation, health checks', have: 'Included, through LiteLLM' },
  { item: 'PII detection and a policy engine', build: 'Detectors, evasion tests, tuning, explanations', have: 'Included, with a shared detector' },
  { item: 'Append-only audit log and exports', build: 'Schema, retention, access control, SIEM mapping', have: 'Included, with SIEM and OpenTelemetry export' },
  { item: 'Budgets and rate limits per team', build: 'Counters, pre-checks before streaming, reporting', have: 'Included' },
  { item: 'MCP tool governance', build: 'Pinning, scanning, grants, taint rules', have: 'Included' },
  { item: 'Keeping up as provider APIs change', build: 'Your team, indefinitely', have: 'Shared with the open-source project' },
];

export default function BuildVsBuySection() {
  return (
    <Section id="build-vs-buy" label="§02 · build or adopt" title={<>What this replaces <em>on your roadmap.</em></>} aside="no invented timelines">
      <div className="opa-card tbl-scroll">
        <table className="tbl">
          <thead>
            <tr><th scope="col">Capability</th><th scope="col">If you build it</th><th scope="col">With OpenProxyAI</th></tr>
          </thead>
          <tbody>
            {ROWS.map(r => (
              <tr key={r.item}><td>{r.item}</td><td>{r.build}</td><td style={{ color: 'var(--accent)' }}>{r.have}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        We give no week counts because we cannot source them. For a longer treatment, read{' '}
        <a href={docsPage('/blog/build-vs-buy-llm-gateway')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Build vs. buy an LLM gateway →</a>
      </p>
    </Section>
  );
}
