import Section from '../components/Section';
import { docsPage } from '../lib/links';

interface Qa {
  q: string;
  a: string;
}

const FAQS: Qa[] = [
  { q: 'What is OpenProxyAI?', a: 'A control layer between your people, your applications and the AI models they use. It applies your rules, protects sensitive data, controls cost and keeps a record of everything.' },
  { q: 'Where does it run?', a: 'In your own environment: your cloud, your data center, or fully offline. There is no hosted service and no vendor in the middle.' },
  { q: 'Which AI models can we use?', a: 'Hosted providers such as OpenAI, Anthropic and Azure OpenAI, models you run yourself, and over a hundred more.' },
  { q: 'Will it work with the AI tools we already use?', a: 'Any tool or application that can call an OpenAI-compatible service can be pointed at it by changing one address and one key.' },
  { q: 'Does it keep our prompts?', a: 'Not by default. The record keeps who asked, which model, how much it cost and what the policy decided. Keeping redacted samples of prompts and answers is an option you turn on.' },
  { q: 'Will it slow our AI tools down?', a: 'It adds a small amount of time because it checks each request first. We publish no figure yet because we have no benchmark anyone can reproduce. You can measure it yourself in the demo.' },
  { q: 'Is it certified or compliant?', a: 'No. OpenProxyAI holds no SOC 2, ISO 27001 or HIPAA certification. The compliance templates are configurations that help you document your controls.' },
  { q: 'How is it different from other AI gateways?', a: 'Our focus is governance you host yourself: sensitive data kept where you allow, tightly controlled AI agents, and a permanent record. Each comparison article is dated and says when another tool fits better.' },
  { q: 'What does it cost?', a: 'The code is open source and free. Paid plans raise limits on users, keys and record retention, and add single sign-on and compliance templates. See the pricing page.' },
];

export default function FaqSection() {
  return (
    <Section id="faq" label="Questions" title={<>Questions leaders <em>ask first.</em></>} aside="straight answers">
      <div className="faq">
        {FAQS.map(item => (
          <details key={item.q}>
            <summary>{item.q}</summary>
            <p>{item.a}</p>
          </details>
        ))}
      </div>
      <p className="note">
        More answers in the{' '}
        <a href={docsPage('/resources/faq')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>documentation FAQ →</a>
      </p>
    </Section>
  );
}
