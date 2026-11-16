import Section from '../components/Section';
import { docsPage } from '../lib/links';

interface Industry {
  name: string;
  template: string;
  text: string;
}

const INDUSTRIES: Industry[] = [
  { name: 'Financial services', template: 'Card-data template', text: 'Block payment-card data, keep transaction context in the record and apply stricter limits by default.' },
  { name: 'Healthcare', template: 'Health-privacy template', text: 'Detect health information, redact it in answers and keep the record your privacy team needs.' },
  { name: 'Public sector', template: 'Government template', text: 'Block classified markings, redact personal data and set a long retention target. Assign approved regions yourself.' },
];

const GUIDES = [
  { label: 'EU AI Act for engineers', slug: 'eu-ai-act-for-engineers' },
  { label: 'Quebec Law 25 and AI providers', slug: 'quebec-law-25-ai-providers' },
  { label: 'HIPAA and LLMs', slug: 'hipaa-and-llms' },
];

export default function IndustriesSection() {
  return (
    <Section id="industries" label="Regulated industries" title={<>Built for teams that <em>answer to regulators.</em></>} aside="templates, not certifications">
      <div className="grid-3">
        {INDUSTRIES.map(i => (
          <div key={i.name} className="opa-card" style={{ padding: 22 }}>
            <h3 style={{ margin: '0 0 4px', color: 'var(--ink)', fontSize: 17, fontWeight: 600 }}>{i.name}</h3>
            <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent)', marginBottom: 10 }}>{i.template}</div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{i.text}</p>
          </div>
        ))}
      </div>
      <p className="note" style={{ maxWidth: '78ch' }}>
        The templates are starting points you review and enforce yourself. They help you document your controls. They do not make a deployment compliant, and OpenProxyAI holds no certification.
      </p>
      <p className="note">
        Background reading:{' '}
        {GUIDES.map((g, i) => (
          <span key={g.slug}>
            {i > 0 && ' · '}
            <a href={docsPage(`/blog/${g.slug}`)} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>{g.label}</a>
          </span>
        ))}
        . General information, not legal advice.
      </p>
    </Section>
  );
}
