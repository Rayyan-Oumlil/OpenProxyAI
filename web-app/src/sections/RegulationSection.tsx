import Section from '../components/Section';
import { docsPage } from '../lib/links';

const TOPICS = [
  { title: 'EU AI Act', text: 'Article 12 asks high-risk systems to record events automatically. A gateway log helps you document what your AI did. It does not by itself make a system compliant.', href: docsPage('/blog/eu-ai-act-for-engineers'), label: 'EU AI Act for engineers' },
  { title: 'Quebec Law 25', text: 'Before personal information leaves Quebec, a privacy impact assessment is required. Data-class routing and residency tags help you control and show where prompts go.', href: docsPage('/blog/quebec-law-25-ai-providers'), label: 'Law 25 and AI providers' },
  { title: 'HIPAA', text: 'Policy templates and response redaction help you build the technical controls. The legal obligations stay with you and your agreements with each provider.', href: docsPage('/blog/hipaa-and-llms'), label: 'HIPAA and LLMs' },
];

export default function RegulationSection() {
  return (
    <Section id="regulation" label="§06 · regulation" title={<>Rules you may face, <em>and what helps.</em></>} aside="general information, not legal advice">
      <div className="grid-3">
        {TOPICS.map(t => (
          <div key={t.title} className="opa-card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500 }}>{t.title}</div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)', flex: 1 }}>{t.text}</p>
            <a href={t.href} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', fontSize: 12.5, textDecoration: 'none' }}>{t.label} →</a>
          </div>
        ))}
      </div>
    </Section>
  );
}
