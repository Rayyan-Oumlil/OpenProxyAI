import Section from '../components/Section';
import { docsPage } from '../lib/links';

const LIMITS = [
  { title: 'No certification', text: 'OpenProxyAI holds no SOC 2, ISO 27001 or HIPAA certification, and the FedRAMP-aligned template is not a FedRAMP authorization.' },
  { title: 'Templates are starting points', text: 'The Healthcare, Finance and Government templates are policy configurations you review, adjust and enforce. They help you document your controls. They do not make a deployment compliant.' },
  { title: 'You operate it', text: 'It is self-hosted, so patching, backups, network boundaries and access to the host are yours. The gateway enforces policy; it cannot secure infrastructure it does not run.' },
  { title: 'Detection is not perfect', text: 'Detection of personal data and manipulation attempts reduces risk, but no detector catches everything. Treat it as a layer, not a guarantee.' },
];

export default function LimitsSection() {
  return (
    <Section id="limits" label="Limits" title={<>What it <em>does not</em> do.</>} aside="the part vendors skip">
      <div className="grid-2">
        {LIMITS.map(l => (
          <div key={l.title} className="opa-card" style={{ padding: 20 }}>
            <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500, marginBottom: 6 }}>{l.title}</div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)' }}>{l.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        <a href={docsPage('/security/trust-center')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Read the trust center →</a>
      </p>
    </Section>
  );
}
