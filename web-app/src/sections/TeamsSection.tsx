import Section from '../components/Section';

const ITEMS = [
  { title: 'Shared conversations', text: 'Organize AI conversations by project, with tags, search, personas and sharing. A conversation can move to another model without exposing sensitive history to one with less clearance.' },
  { title: 'Large batch jobs', text: 'Run big workloads under the same rules and the same budget as everything else, with progress, cost and a cancel button for administrators.' },
  { title: 'Side-by-side testing', text: 'Try a prompt on several models at once in a built-in workspace, with your policy applied, before anyone depends on the result.' },
  { title: 'Smarter routing', text: 'Choose models by sensitivity, region or measured quality. When a provider has trouble, traffic moves to the others automatically, within your rules.' },
  { title: 'Reporting', text: 'Usage and spend by team, person and model, alerts for unusual cost, and a compliance export for your records.' },
  { title: 'Protected administration', text: 'Limits on sign-in attempts, restricted access to technical metrics, and only owners or administrators can revoke access keys.' },
];

export default function TeamsSection() {
  return (
    <Section id="teams" label="For your teams" title={<>Built for how <em>organizations actually work.</em></>} aside="shared, governed, reported">
      <div className="grid-3">
        {ITEMS.map(i => (
          <div key={i.title} className="opa-card" style={{ padding: 22 }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{i.title}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{i.text}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}
