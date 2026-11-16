import Section from '../components/Section';

const WITHOUT = [
  'Provider keys are copied into every app, script and notebook.',
  'Nobody can say which prompts left the building, or where they went.',
  'A sensitive prompt can reach any model, including a cheap public one.',
  'Spend is a surprise on the invoice, not a limit you set.',
];

const WITH = [
  'One endpoint. Provider keys stay inside the gateway.',
  'Every request is logged: who, which model, what it cost, what policy decided.',
  'Each request gets a data class. Only approved models may serve it, with no silent fallback.',
  'Budgets and rate limits per org, team, user and model, checked before the call.',
];

function Column({ title, items, tone }: { title: string; items: string[]; tone: 'bad' | 'good' }) {
  const color = tone === 'good' ? 'var(--accent)' : 'var(--err)';
  return (
    <div className="opa-card" style={{ padding: 22 }}>
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.14em', color, marginBottom: 14 }}>{title}</div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map(item => (
          <li key={item} style={{ display: 'flex', gap: 10, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.55, color: 'var(--ink-2)' }}>
            <span style={{ color }} aria-hidden="true">{tone === 'good' ? '✓' : '×'}</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ProblemSection() {
  return (
    <Section id="problem" label="§01 · the problem" title={<>Your teams already call LLMs. <em>Can you show how?</em></>} aside="before and after">
      <div className="grid-2">
        <Column title="without a gateway" items={WITHOUT} tone="bad" />
        <Column title="with openproxyai" items={WITH} tone="good" />
      </div>
    </Section>
  );
}
