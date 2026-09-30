import { Link } from 'react-router';
import Section from '../../components/Section';
import ControlMap from '../../map/ControlMap';
import { SCENES } from '../../map/scenes';

const PILLARS = [
  { to: '/models', scene: SCENES.models, title: 'Models', body: 'Routing, failover, caching, budgets and data residency for every LLM call.' },
  { to: '/agents', scene: SCENES.agents, title: 'Agents', body: 'Identity, tool policies and audit for agents calling MCP tool servers.' },
  { to: '/trust', scene: SCENES.trust, title: 'Trust', body: 'PII redaction, injection detection, tenant isolation and a tamper-evident log.' },
] as const;

export default function Pillars() {
  return (
    <Section title="Govern the models, the agents, and the evidence.">
      <ul className="grid gap-4 md:grid-cols-3">
        {PILLARS.map(p => (
          <li key={p.to}>
            <Link to={p.to} className="group block h-full rounded-xl border border-line bg-surface p-5 hover:border-ink-dim">
              <ControlMap scene={p.scene} animate={false} className="pointer-events-none opacity-80" />
              <h3 className="mt-4 text-step-1 font-semibold group-hover:text-signal">{p.title}</h3>
              <p className="mt-2 text-ink-dim">{p.body}</p>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}
