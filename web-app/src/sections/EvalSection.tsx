import Section from '../components/Section';
import { docsPage } from '../lib/links';

const PARTS = [
  { title: 'Feedback', text: 'An application rates an answer with its own API key through POST /v1/feedback.' },
  { title: 'Datasets', text: 'Build evaluation datasets from captured traffic. Payload capture is opt-in and stores redacted samples only.' },
  { title: 'Evaluators and runs', text: 'Score a dataset against a model or prompt, and compare runs.' },
  { title: 'Adaptive A/B', text: 'Experiments shift traffic toward the better variant and stop when there is a winner.' },
  { title: 'Promotion gate', text: 'A prompt can be required to pass an evaluation before it is promoted.' },
];

export default function EvalSection() {
  return (
    <Section id="evals" label="§05 · evaluation loop" title={<>Know a change is better <em>before you ship it.</em></>} aside="built into the gateway">
      <div className="grid-3">
        {PARTS.map(p => (
          <div key={p.title} className="opa-card" style={{ padding: 20 }}>
            <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500, marginBottom: 6 }}>{p.title}</div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 13.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{p.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        <a href={docsPage('/guides/adaptive-experiments')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Adaptive experiments guide →</a>
      </p>
    </Section>
  );
}
