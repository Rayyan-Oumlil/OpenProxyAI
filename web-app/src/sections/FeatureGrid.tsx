import { Shield, GitBranch, Plug, Gauge, Layers, FlaskConical, SlidersHorizontal, Route, MessagesSquare, Users, ScrollText, Server } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import Section from '../components/Section';
import { docsPage, repoFile } from '../lib/links';

interface Feature {
  icon: LucideIcon;
  title: string;
  text: string;
}

const FEATURES: Feature[] = [
  { icon: Shield, title: 'Policies and guardrails', text: 'Block personal data, sensitive words and attempts to trick the AI. Approve the models people may use, check answers before users see them, and add your own custom rules.' },
  { icon: GitBranch, title: 'Protection by sensitivity', text: 'Four sensitivity levels decide which models may see what. Preview any rule on a sample request before you enforce it.' },
  { icon: Plug, title: 'Control of AI agents', text: 'Approve the tools agents can use, lock their definitions, screen the results and give each team its own set.' },
  { icon: Gauge, title: 'Budgets and limits', text: 'Usage and spending limits by company, team, person and model, with alerts for unusual spend and regular reports.' },
  { icon: Layers, title: 'Every kind of AI work', text: 'Chat, search, images, audio, real-time voice and large batch jobs, all under the same rules and the same record.' },
  { icon: FlaskConical, title: 'Quality and testing', text: 'Collect feedback, build test sets from real use, score answers and compare models side by side. Approve a prompt only when it passes.' },
  { icon: SlidersHorizontal, title: 'Control how models behave', text: 'Set defaults and ceilings for creativity, depth of reasoning, answer length and citations, by team.' },
  { icon: Route, title: 'Smarter routing and reliability', text: 'Send each request to the right model by sensitivity, region or measured quality. Fail over automatically when a provider has trouble, and reuse answers to cut cost.' },
  { icon: MessagesSquare, title: 'Shared conversations', text: 'Organize AI conversations by project, with tags, search, personas and sharing, and no leak of sensitive history to a model with less clearance.' },
  { icon: Users, title: 'People and access', text: 'Roles, single sign-on and automatic user provisioning with Okta or Entra ID. Each organization’s data is kept separate.' },
  { icon: ScrollText, title: 'Audit and reporting', text: 'A lasting record of every request, spend reports, and export to your security monitoring tools.' },
  { icon: Server, title: 'Your environment, your console', text: 'Run it in your cloud, your data center or fully offline. More than twenty admin screens give your team everything in one place.' },
];

export default function FeatureGrid() {
  return (
    <Section id="features" label="Capabilities" title={<>Everything you need to run AI <em>responsibly.</em></>} aside="one platform">
      <div className="grid-3 feature-grid">
        {FEATURES.map(f => (
          <div key={f.title} className="opa-card" style={{ padding: 22 }}>
            <span style={{ width: 38, height: 38, borderRadius: 10, background: 'color-mix(in srgb, var(--accent) 12%, var(--bg))', color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 12 }}>
              <f.icon size={19} aria-hidden="true" />
            </span>
            <h3 style={{ margin: '0 0 6px', color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{f.title}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{f.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        <a href={repoFile('docs/features.md')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Full feature list →</a>{' '}
        <a href={docsPage('/getting-started/introduction')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', marginLeft: 12 }}>Introduction to the documentation →</a>
      </p>
    </Section>
  );
}
