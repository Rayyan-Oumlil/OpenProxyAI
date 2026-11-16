import { BookOpen, Rocket, Workflow, ShieldCheck, Braces, Newspaper } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import Section from '../components/Section';
import { docsPage } from '../lib/links';

interface DocCard {
  icon: LucideIcon;
  title: string;
  text: string;
  href: string;
}

const CARDS: DocCard[] = [
  { icon: Rocket, title: 'Get started', text: 'Set it up and send a first request.', href: docsPage('/getting-started/quickstart') },
  { icon: Workflow, title: 'How it works', text: 'How requests are checked, how policies work, and how routing, caching and budgets behave.', href: docsPage('/core-concepts/request-pipeline') },
  { icon: BookOpen, title: 'Guides', text: 'AI agent tools, single sign-on, secrets managers, security monitoring and experiments.', href: docsPage('/guides/mcp-gateway') },
  { icon: Braces, title: 'For developers', text: 'The full API reference for your engineering teams.', href: docsPage('/api-reference/overview') },
  { icon: ShieldCheck, title: 'Security and trust', text: 'What we certify and what we do not, how data is protected, and where it stays.', href: docsPage('/security/trust-center') },
  { icon: Newspaper, title: 'Blog', text: 'More than a hundred articles on regulation, AI risk, comparisons and how-tos.', href: docsPage('/blog') },
];

export default function DocsBandSection() {
  return (
    <Section id="docs" label="Documentation" title={<>Documentation your teams <em>can rely on.</em></>} aside="docs.openproxyai.com">
      <div className="grid-3">
        {CARDS.map(c => (
          <a key={c.title} className="opa-card" href={c.href} target="_blank" rel="noopener noreferrer" style={{ padding: 20, display: 'block', textDecoration: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, color: 'var(--ink)' }}>
              <c.icon size={18} color="var(--accent)" aria-hidden="true" />
              <span style={{ fontSize: 14, fontWeight: 500 }}>{c.title} <span style={{ color: 'var(--accent)' }}>→</span></span>
            </div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 13.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{c.text}</p>
          </a>
        ))}
      </div>
    </Section>
  );
}
