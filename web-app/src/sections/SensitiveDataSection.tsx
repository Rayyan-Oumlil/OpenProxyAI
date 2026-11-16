import Section from '../components/Section';

const LEVELS = [
  { name: 'Public', note: 'Any approved model', level: 1 },
  { name: 'Internal', note: 'The default level', level: 2 },
  { name: 'Confidential', note: 'For example a social security or card number', level: 3 },
  { name: 'Secret', note: 'Only models you cleared for it', level: 4 },
];

const EXAMPLE = [
  { label: 'A user writes', value: '“Customer SSN is 123-45-6789, draft a reply.”' },
  { label: 'OpenProxyAI detects', value: 'Confidential data: a social security number' },
  { label: 'Your policy decides', value: 'Blocked. Nothing is sent to any AI model.' },
  { label: 'The user is told', value: '“This request appears to contain personal or sensitive data that your organization’s policy does not allow to be sent.”' },
  { label: 'The record shows', value: 'Who asked, when, what was detected and why it was blocked.' },
];

export default function SensitiveDataSection() {
  return (
    <Section id="sensitive-data" label="Data protection" title={<>Sensitive data only goes <em>where you allow.</em></>} aside="with a reason every time">
      <div className="split">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <p className="lede">
            Every request is classified by sensitivity. You decide which AI models may handle each level. If no approved model can handle a request, it is refused with a clear reason. It is never quietly sent somewhere else.
          </p>
          <div className="ladder" role="list" aria-label="Sensitivity levels, lowest to highest">
            {LEVELS.map(l => (
              <div key={l.name} className="ladder-step" data-level={l.level} role="listitem">
                {l.name}
                <small>{l.note}</small>
              </div>
            ))}
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12, fontFamily: 'var(--sans)', fontSize: 15, lineHeight: 1.6, color: 'var(--ink-2)' }}>
            <li><strong style={{ color: 'var(--ink)' }}>No silent fallback.</strong> A refused request stays refused.</li>
            <li><strong style={{ color: 'var(--ink)' }}>Explained to the user.</strong> People see a plain sentence, not an error code.</li>
            <li><strong style={{ color: 'var(--ink)' }}>Preview before you enforce.</strong> Test any rule on a sample request before you turn it on.</li>
          </ul>
        </div>

        <div className="opa-card" style={{ padding: 22 }}>
          <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--ink-3)', marginBottom: 14 }}>What happens to one risky request</div>
          <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
            {EXAMPLE.map((step, i) => (
              <li key={step.label} style={{ display: 'grid', gridTemplateColumns: '28px minmax(0,1fr)', gap: 12 }}>
                <span style={{ width: 26, height: 26, borderRadius: '50%', background: i === 2 ? 'var(--err)' : 'var(--panel-2)', color: i === 2 ? '#fff' : 'var(--ink-2)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 600 }}>{i + 1}</span>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{step.label}</div>
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 15, lineHeight: 1.5, color: 'var(--ink)' }}>{step.value}</div>
                </div>
              </li>
            ))}
          </ol>
          <p className="note">Taken from the demo. The wording of the message is yours to change.</p>
        </div>
      </div>
    </Section>
  );
}
