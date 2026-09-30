import Section from '../../components/Section';

const TARGETS = [
  { title: 'Your cloud', body: 'Helm chart with autoscaling, disruption budgets and migrations run as an init step.' },
  { title: 'Your cluster', body: 'Bring your own PostgreSQL and Redis. No managed dependencies required.' },
  { title: 'Air-gapped', body: 'AIRGAP_MODE turns off every outbound sidecar. Only the model calls you allow leave the network.' },
];

export default function Deploy() {
  return (
    <Section title="Runs where your data is allowed to be.">
      <ul className="grid gap-x-12 md:grid-cols-3">
        {TARGETS.map(t => (
          <li key={t.title} className="border-t border-line py-6">
            <h3 className="text-step-1 font-semibold">{t.title}</h3>
            <p className="mt-2 text-ink-dim">{t.body}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}
