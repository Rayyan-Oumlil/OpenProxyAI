import Section from '../components/Section';

const STEPS = [
  { t: 'A key starts failing', d: 'Health checks ping each provider key and mark it unhealthy after repeated failures.' },
  { t: 'The router stops choosing it', d: 'An unhealthy key leaves the candidate set, and a circuit breaker keeps a failing key from being hammered.' },
  { t: 'Traffic uses the remaining keys', d: 'Healthy keys take the load by weight. Failover respects your organization’s region and, with routing enforced, the data class: a request is never retried on a key your policy does not allow.' },
  { t: 'The key recovers', d: 'When its checks pass again it returns to rotation at its configured weight.' },
];

export default function FailoverSection() {
  return (
    <Section id="failover" label="§02 · failover" title={<>One key fails. <em>The rules still hold.</em></>} aside="example scenario">
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {STEPS.map((s, i) => (
          <div key={s.t} style={{ display: 'grid', gridTemplateColumns: '32px minmax(0,1fr)', gap: 14, padding: '12px 0', borderBottom: i < STEPS.length - 1 ? '1px solid var(--line)' : 'none' }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--accent)' }}>{String(i + 1).padStart(2, '0')}</span>
            <div>
              <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500, marginBottom: 2 }}>{s.t}</div>
              <div style={{ color: 'var(--ink-2)', fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6 }}>{s.d}</div>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}
