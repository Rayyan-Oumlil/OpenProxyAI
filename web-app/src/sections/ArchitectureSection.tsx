import Section from '../components/Section';

const HOPS = [
  { n: '1', title: 'Your people and applications', desc: 'Employees, internal tools and AI agents keep using the AI tools they know. They only change where requests are sent.' },
  { n: '2', title: 'OpenProxyAI', desc: 'Checks who is asking, applies your rules and limits, picks an approved model and records the outcome, inside your own environment.' },
  { n: '3', title: 'AI models and tools', desc: 'Hosted providers, models you run yourself and the business tools your agents use. Only the destinations you approved can be reached.' },
];

export default function ArchitectureSection() {
  return (
    <Section id="architecture" label="How it fits" title={<>One layer between <em>what you have and what you use.</em></>} aside="runs in your environment">
      <div className="grid-3">
        {HOPS.map(h => (
          <div key={h.n} className="opa-card" style={{ padding: 22 }}>
            <span style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 600, marginBottom: 12 }}>{h.n}</span>
            <h3 style={{ margin: '0 0 6px', color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{h.title}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{h.desc}</p>
          </div>
        ))}
      </div>
      <p className="note">It runs as a service next to a database and a cache that your team operates, and it scales out as demand grows.</p>
    </Section>
  );
}
