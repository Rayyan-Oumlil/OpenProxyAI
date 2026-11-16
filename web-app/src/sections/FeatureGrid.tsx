import { Shield, GitBranch, Plug, Gauge, Layers, FlaskConical, MessagesSquare, Users, ScrollText, Zap, Server, LayoutDashboard } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import Section from '../components/Section';
import { docsPage, repoFile } from '../lib/links';

interface Feature {
  icon: LucideIcon;
  title: string;
  text: string;
}

const FEATURES: Feature[] = [
  { icon: Shield, title: 'Policy engine', text: 'PII and keyword blocking, prompt-injection detection, response guardrails, model allowlists and sandboxed WebAssembly plugins. Blocks return HTTP 446 with an explanation.' },
  { icon: GitBranch, title: 'Data-class routing', text: 'public, internal, confidential, secret. A model registry decides who may serve each class, with no silent fallback and a policy preview.' },
  { icon: Plug, title: 'MCP gateway', text: 'One endpoint for all tool servers, with tool pinning, injection scanning, per-caller grants, virtual bundles and taint tracking.' },
  { icon: Gauge, title: 'Budgets and limits', text: 'Rate limits and budgets per org, team, user and model, checked before the call, plus anomaly alerts and spend reports.' },
  { icon: Layers, title: 'Every endpoint', text: 'Chat with streaming, embeddings, rerank, images, audio, Responses, files and batches, and a realtime WebSocket.' },
  { icon: FlaskConical, title: 'Evaluation loop', text: 'Feedback, datasets, evaluators, eval runs, adaptive A/B experiments and a prompt promotion gate.' },
  { icon: MessagesSquare, title: 'Conversations', text: 'Threads that survive a model switch without leaking more-sensitive history to a model with less clearance.' },
  { icon: Users, title: 'Identity and isolation', text: 'Roles, OIDC single sign-on, SCIM 2.0 and Postgres row-level security that scopes every query to one organization.' },
  { icon: ScrollText, title: 'Audit and export', text: 'Append-only logs, a request trace for every call, SIEM export (CEF, JSON, syslog) and OpenTelemetry gen_ai spans.' },
  { icon: Zap, title: 'Caching and failover', text: 'A three-tier cache (off by default), weighted key rotation, health checks and a circuit breaker.' },
  { icon: Server, title: 'Operations', text: 'Docker Compose, a Helm chart, air-gap mode, Vault and AWS Secrets Manager for provider keys, and Prometheus metrics.' },
  { icon: LayoutDashboard, title: 'Admin console', text: 'More than twenty screens: dashboard, request trace, policy, registry, MCP, datasets, experiments, teams and billing limits.' },
];

export default function FeatureGrid() {
  return (
    <Section id="features" label="§06 · in the box" title={<>Everything a gateway needs, <em>and the governance on top.</em></>} aside="full inventory in the repo">
      <div className="grid-3 feature-grid">
        {FEATURES.map(f => (
          <div key={f.title} className="opa-card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <span style={{ width: 32, height: 32, borderRadius: 8, background: 'color-mix(in srgb, var(--accent) 14%, var(--panel-2))', color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                <f.icon size={17} aria-hidden="true" />
              </span>
              <h3 style={{ margin: 0, color: 'var(--ink)', fontSize: 14, fontWeight: 500 }}>{f.title}</h3>
            </div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 13.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{f.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        <a href={repoFile('docs/features.md')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Full feature inventory →</a>{' '}
        <a href={docsPage('/getting-started/introduction')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', marginLeft: 12 }}>Introduction to the docs →</a>
      </p>
    </Section>
  );
}
