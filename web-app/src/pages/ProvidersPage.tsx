import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PageCta from '../components/PageCta';
import Section from '../components/Section';
import FlowDiagram from '../components/FlowDiagram';
import { Steps } from '../components/blocks';
import FailoverSection from '../sections/FailoverSection';

const KINDS = [
  { title: 'AI models', body: 'The hosted AI models your teams call, and the models you run yourself. You add each one to the model registry, and only those can be reached. Your applications ask for a model by name and you decide which account serves it.', chips: ['OpenAI and Azure OpenAI', 'Anthropic', 'Google', 'Mistral', 'Cohere', 'Groq', 'Models you run yourself', 'Over a hundred more'] },
  { title: 'Where requests come from', body: 'Chat assistants, coding assistants, your internal applications and AI agents. They keep working as before; their requests simply pass through the checkpoint first. Any tool that can call an OpenAI-compatible service works.', chips: ['Chat assistants', 'Coding assistants', 'Internal applications', 'AI agents'] },
  { title: 'Tools that agents use', body: 'The systems an AI agent can act on: files, messages, records. Each agent is limited to the tools on its approved list, and a tool that changes after approval is blocked until it is reviewed.', chips: ['Files', 'Messages', 'Records'] },
  { title: 'Your existing systems', body: 'The sign-in your staff already use, the place your security team already keeps its logs, and the secrets manager that holds your provider keys. The audit record can be exported for them.', chips: ['Okta', 'Microsoft Entra ID', 'SIEM export', 'OpenTelemetry', 'HashiCorp Vault', 'AWS Secrets Manager'] },
];

const CONNECT = [
  { title: 'Send requests through it', body: 'Your applications and assistants are pointed at OpenProxyAI inside your environment, instead of straight at the AI model. One address and one key change.' },
  { title: 'Register what you approve', body: 'Add the AI models and the tools your organization has approved, each with its region and the highest sensitivity it may handle.' },
  { title: 'Set your rules', body: 'Start in Observe mode. Move to Enforce when you are satisfied with what you see.' },
];

export default function ProvidersPage() {
  useEffect(() => { document.title = 'Integrations and models | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Integrations"
        title={<>It fits around the AI <span style={{ color: 'var(--soft)' }}>you already use.</span></>}
        description="OpenProxyAI does not replace your AI models or assistants. It sits in front of them, so your teams keep the tools they know and you gain one place to control them."
        secondary={{ label: 'How connecting works', href: '#connect' }}
        visual={<FlowDiagram />}
      />
      <Section id="works-with" label="What it works with" title="Four kinds of connection." aside="Model names are not listed because they change faster than this page.">
        <div>
          {KINDS.map((k, i) => (
            <div key={k.title} style={{ borderTop: '1px solid var(--line)', padding: '36px 0', display: 'flex', flexWrap: 'wrap', gap: '24px 56px' }}>
              <div style={{ flex: '1 1 340px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <span className="mono" style={{ fontSize: 13, color: 'var(--ink-3)' }}>{String(i + 1).padStart(2, '0')}</span>
                <h3 style={{ margin: 0, fontSize: 26, fontWeight: 500, letterSpacing: '-0.02em' }}>{k.title}</h3>
                <p style={{ margin: 0, fontSize: 16, color: 'var(--ink-2)', textWrap: 'pretty' }}>{k.body}</p>
              </div>
              <ul style={{ flex: '1 1 380px', minWidth: 0, listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexWrap: 'wrap', gap: 10, alignContent: 'flex-start' }}>
                {k.chips.map(c => (
                  <li key={c} style={{ padding: '11px 18px', border: '1px solid var(--line-2)', borderRadius: 14, background: 'var(--bg-2)', fontSize: 15, fontWeight: 500 }}>{c}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>
      <Section id="connect" label="How connecting works" title="Three steps, and nothing changes for your staff.">
        <Steps items={CONNECT} min={260} />
      </Section>
      <FailoverSection />
      <PageCta title="Tell us what you run. We will show you how it connects." body="Bring the list of AI models and tools your teams use today." />
    </>
  );
}
