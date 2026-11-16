import Section from '../components/Section';

const TEMPLATES = [
  { name: 'Healthcare', tag: 'HIPAA-aligned', desc: 'Detects clinical terms and health information, redacts it in answers and enforces your rules. You choose the approved models.' },
  { name: 'Finance', tag: 'PCI-aligned', desc: 'Blocks payment-card data, keeps transaction context in the record and applies stricter limits by default.' },
  { name: 'Government', tag: 'FedRAMP-aligned', desc: 'Blocks classified markings, redacts personal data and sets a three-year retention target. You assign the approved regions.' },
];

export default function ComplianceSection() {
  return (
    <Section id="templates" label="Templates" title={<>Compliance templates <em>you configure.</em></>} aside="templates, not certifications">
      <p className="lede" style={{ marginBottom: 24 }}>
        Ready-made rule sets aligned to common framework requirements. Apply one, review every rule and enforce it yourself.
      </p>
      <div className="opa-card">
        {TEMPLATES.map((t, i) => (
          <div key={t.name} className="data-row tmpl-row" style={{ display: 'grid', gridTemplateColumns: '140px 130px minmax(0,1fr)', gap: 16, padding: '14px 18px', borderBottom: i < TEMPLATES.length - 1 ? '1px solid var(--line)' : 'none', fontSize: 14.5, alignItems: 'center' }}>
            <span style={{ color: 'var(--ink)', fontWeight: 600 }}>{t.name}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{t.tag}</span>
            <span style={{ color: 'var(--ink-2)' }}>{t.desc}</span>
          </div>
        ))}
      </div>
      <style>{`@media (max-width: 1000px) { .tmpl-row { grid-template-columns: minmax(0,1fr) !important; gap: 4px !important; } }`}</style>
    </Section>
  );
}
