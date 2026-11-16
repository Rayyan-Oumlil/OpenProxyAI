import Section from '../components/Section';

const TEMPLATES = [
  { name: 'Healthcare', tag: 'HIPAA-aligned', desc: 'Clinical keywords and PHI entities in enforce mode, response redaction. Set your own model allowlist.' },
  { name: 'Finance', tag: 'PCI-aligned', desc: 'Cardholder data blocking, transaction-context logging, stricter rate limits by default.' },
  { name: 'Government', tag: 'FedRAMP-aligned', desc: 'Classified-marking keyword blocking, PII redaction, a 3-year retention target. Assign US-region provider keys yourself.' },
];

export default function ComplianceSection() {
  return (
    <Section id="templates" label="§03 · templates" title={<>Compliance templates <em>you configure.</em></>} aside="templates · not certifications">
      <p className="lede" style={{ marginBottom: 24 }}>
        Pre-built policy configurations aligned to common framework requirements. Apply one, review every rule, and enforce it yourself.
      </p>
      <div className="opa-card">
        {TEMPLATES.map((t, i) => (
          <div key={t.name} className="data-row tmpl-row" style={{ display: 'grid', gridTemplateColumns: '140px 130px minmax(0,1fr)', gap: 16, padding: '14px 18px', borderBottom: i < TEMPLATES.length - 1 ? '1px solid var(--line)' : 'none', fontSize: 13, alignItems: 'center' }}>
            <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{t.name}</span>
            <span style={{ fontSize: 10.5, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{t.tag}</span>
            <span style={{ color: 'var(--ink-2)' }}>{t.desc}</span>
          </div>
        ))}
      </div>
      <style>{`@media (max-width: 1000px) { .tmpl-row { grid-template-columns: minmax(0,1fr) !important; gap: 4px !important; } }`}</style>
    </Section>
  );
}
