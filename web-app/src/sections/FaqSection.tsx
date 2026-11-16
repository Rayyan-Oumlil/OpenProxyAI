import Section from '../components/Section';
import { docsPage } from '../lib/links';

interface Qa {
  q: string;
  a: string;
}

const FAQS: Qa[] = [
  { q: 'What is OpenProxyAI?', a: 'An open-source LLM gateway. It sits between your applications and model providers, applies policy, data-class routing, budgets and an audit trail to every request, and exposes one OpenAI-compatible endpoint.' },
  { q: 'Is it hosted, or do I run it?', a: 'You run it. It is self-hosted, with Docker Compose, a Helm chart and an air-gap mode. There is no hosted service.' },
  { q: 'Which providers does it support?', a: 'Hosted providers such as OpenAI, Anthropic and Azure OpenAI, any OpenAI-compatible endpoint you run yourself, and 100+ more through LiteLLM.' },
  { q: 'Does it store my prompts?', a: 'Not by default. The audit log keeps metadata: model, tokens, cost, status, data class and the policy decision. Keeping redacted samples of prompts and answers is an opt-in you turn on.' },
  { q: 'Does it add latency?', a: 'Yes, a little: it runs checks before the call. We publish no figure because we have no reproducible benchmark yet. The request trace in the demo console shows the time of each stage on your own hardware.' },
  { q: 'Is it certified or compliant?', a: 'No. OpenProxyAI holds no SOC 2, ISO 27001 or HIPAA certification. The compliance templates are policy configurations that help you document your controls.' },
  { q: 'How is it different from LiteLLM, Portkey or Helicone?', a: 'Our focus is governance you host: data-class routing with no silent fallback, bounded MCP tools and an append-only audit trail. Each comparison post is dated and says when another tool fits better.' },
  { q: 'What does it cost?', a: 'The code is Apache-2.0 and free. Plans change the limits (users, keys, audit retention) and unlock SSO and compliance templates. See the pricing page.' },
];

export default function FaqSection() {
  return (
    <Section id="faq" label="§12 · questions" title={<>Questions people <em>ask first.</em></>} aside="straight answers">
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
