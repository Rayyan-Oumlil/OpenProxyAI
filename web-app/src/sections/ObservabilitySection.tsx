import Section from '../components/Section';
import { docsPage } from '../lib/links';

const SIGNALS = [
  { name: 'Your monitoring tools', desc: 'Usage, cost, speed, policy blocks and limit hits are available to the monitoring tools you already run.' },
  { name: 'Open standard traces', desc: 'One trace for each finished request and each agent tool call, in the OpenTelemetry standard. Prompts and tool inputs are never attached. Off by default.' },
  { name: 'Security event export', desc: 'A security event for every block, budget stop or rate limit, sent to your SIEM in a standard format. Off by default, and a broken receiver cannot slow a request.' },
];

export default function ObservabilitySection() {
  return (
    <Section id="observability" label="Reporting and integrations" title={<>Plugs into <em>what you already run.</em></>} aside="opt-in per deployment">
      <div className="grid-3">
        {SIGNALS.map(s => (
          <div key={s.name} className="opa-card" style={{ padding: 22 }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{s.name}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{s.desc}</p>
          </div>
        ))}
      </div>
      <p className="note">
        <a href={docsPage('/guides/telemetry-and-siem')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--ink)' }}>Monitoring and security export guide →</a>
      </p>
    </Section>
  );
}
