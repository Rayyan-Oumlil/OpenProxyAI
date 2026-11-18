import Section from '../components/Section';
import { docsPage } from '../lib/links';

const PARTS = [
  { title: 'Feedback', text: 'Let applications and users rate answers, so quality is measured rather than guessed.' },
  { title: 'Test sets', text: 'Build evaluation sets from real use. Capturing text is optional and stores redacted samples only.' },
  { title: 'Scoring and comparison', text: 'Score a model or prompt against a test set and compare runs side by side.' },
  { title: 'Live experiments', text: 'Shift traffic toward the better option automatically and stop when there is a clear winner.' },
  { title: 'Approval gate', text: 'Require a prompt to pass its evaluation before it goes live.' },
  { title: 'Behavior settings', text: 'Set defaults and ceilings for creativity, depth of reasoning, answer length and citations, by team.' },
];

export default function EvalSection() {
  return (
    <Section id="evals" label="Quality and testing" title={<>Know a change is better <em>before you roll it out.</em></>} aside="built in">
      <div className="grid-3">
        {PARTS.map(p => (
          <div key={p.title} className="opa-card" style={{ padding: 22 }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{p.title}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{p.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        <a href={docsPage('/guides/adaptive-experiments')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--ink)' }}>Read about experiments →</a>
      </p>
    </Section>
  );
}
