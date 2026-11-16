import Section from '../components/Section';
import { docsPage } from '../lib/links';

const STEPS = [
  {
    title: '1 · Classify',
    text: 'The class is the highest of three things: your org default, the class the caller asserts in the x-openproxy-data-class header (it can only raise it), and the class of each kind of PII the detector finds. Text too large to scan counts as confidential.',
  },
  {
    title: '2 · Register',
    text: 'A model registry lists which models and provider keys may serve each class, and in which regions. Custom endpoints are validated when saved and guarded on every connection, so a private address cannot be reached by mistake.',
  },
  {
    title: '3 · Roll out safely',
    text: 'Routing has three modes: off, log_only and enforce. In log_only the gateway records what it would have refused. The policy preview shows the same decision for any request before you turn enforcement on.',
  },
];

export default function RoutingDetailSection() {
  return (
    <Section id="routing" label="§02 · data-class routing" title={<>Decide where each class of data <em>may go.</em></>} aside="no silent fallback">
      <div className="grid-3">
        {STEPS.map(s => (
          <div key={s.title} className="opa-card" style={{ padding: 20 }}>
            <div style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>{s.title}</div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)' }}>{s.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        A request that no approved model can serve is refused with a reason. It is never rerouted to a model you did not clear for that class.{' '}
        <a href={docsPage('/core-concepts/provider-routing')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Provider routing docs →</a>
      </p>
    </Section>
  );
}
