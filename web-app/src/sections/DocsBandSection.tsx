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
  { icon: Rocket, title: 'Quickstart', text: 'Run it with Docker and send a first request.', href: docsPage('/getting-started/quickstart') },
  { icon: Workflow, title: 'Core concepts', text: 'The request pipeline, policies, provider routing, caching and budgets.', href: docsPage('/core-concepts/request-pipeline') },
  { icon: BookOpen, title: 'Guides', text: 'MCP gateway, SSO and SCIM, secrets from Vault, telemetry and SIEM, experiments.', href: docsPage('/guides/mcp-gateway') },
  { icon: Braces, title: 'API reference', text: 'Chat completions, keys, datasets, eval runs, MCP admin, realtime and error codes.', href: docsPage('/api-reference/overview') },
  { icon: ShieldCheck, title: 'Security', text: 'Trust center, audit logging, row-level security, data residency and templates.', href: docsPage('/security/trust-center') },
  { icon: Newspaper, title: 'Blog', text: 'More than a hundred posts: comparisons, regulation, MCP security and how-tos.', href: docsPage('/blog') },
];

export default function DocsBandSection() {
  return (
    <Section id="docs" label="§11 · documentation" title={<>Documented like a product, <em>not an afterthought.</em></>} aside="docs.openproxyai.com">
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
