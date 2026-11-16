import Section from '../components/Section';
import { docsPage } from '../lib/links';

const ROWS = [
  { item: 'Working with many AI providers', build: 'Each provider’s quirks, keys and outages', have: 'Included, over a hundred providers' },
  { item: 'Detecting and blocking sensitive data', build: 'Detectors, evasion testing, tuning, explanations', have: 'Included' },
  { item: 'A permanent audit record and exports', build: 'Storage, retention, access control, security-tool integration', have: 'Included, with monitoring export' },
  { item: 'Budgets and limits by team', build: 'Counters, checks before each request, reporting', have: 'Included' },
  { item: 'Control of AI agent tools', build: 'Approval, locking, screening, per-team access', have: 'Included' },
  { item: 'Keeping up as provider APIs change', build: 'Your team, indefinitely', have: 'Shared with the open-source project' },
];

export default function BuildVsBuySection() {
  return (
    <Section id="build-vs-buy" label="Build or adopt" title={<>What this replaces <em>on your roadmap.</em></>} aside="no invented timelines">
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
