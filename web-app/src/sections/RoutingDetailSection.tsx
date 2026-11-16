import Section from '../components/Section';
import { docsPage } from '../lib/links';

const STEPS = [
  { title: '1 · Classify', text: 'Each request gets a sensitivity level from three sources: your default, what the application says, and what is detected in the text, such as a card or social security number.' },
  { title: '2 · Approve', text: 'You list which models, accounts and regions may handle each level. A private model of your own can be reserved for the most sensitive data.' },
  { title: '3 · Roll out safely', text: 'Start by observing, then record what would be refused, then enforce. A preview shows the decision for any sample request before you switch anything on.' },
];

export default function RoutingDetailSection() {
  return (
    <Section id="routing" label="Data protection" title={<>Decide where each type of data <em>may go.</em></>} aside="no silent fallback">
      <div className="grid-3">
        {STEPS.map(s => (
          <div key={s.title} className="opa-card" style={{ padding: 22 }}>
            <div style={{ color: 'var(--accent)', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{s.title}</div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{s.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        A request that no approved model can handle is refused with a reason. It is never rerouted to a model you did not clear.{' '}
        <a href={docsPage('/core-concepts/provider-routing')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Read more →</a>
      </p>
    </Section>
  );
}
