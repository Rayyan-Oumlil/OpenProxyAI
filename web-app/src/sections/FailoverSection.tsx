import Section from '../components/Section';

const STEPS = [
  { t: 'An account starts failing', d: 'Regular health checks mark a provider account unhealthy after repeated failures.' },
  { t: 'Traffic stops going there', d: 'The unhealthy account is taken out of rotation, and a circuit breaker stops it from being hammered.' },
  { t: 'Other accounts take the load', d: 'Healthy accounts share the traffic. Failover respects your region and your sensitivity rules: a request is never retried somewhere your policy does not allow.' },
  { t: 'It recovers', d: 'When its checks pass again, it returns to rotation automatically.' },
];

export default function FailoverSection() {
  return (
    <Section id="failover" label="Reliability" title={<>A provider has trouble. <em>Your rules still hold.</em></>} aside="example scenario">
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {STEPS.map((s, i) => (
          <div key={s.t} style={{ display: 'grid', gridTemplateColumns: '32px minmax(0,1fr)', gap: 14, padding: '12px 0', borderBottom: i < STEPS.length - 1 ? '1px solid var(--line)' : 'none' }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink)' }}>{String(i + 1).padStart(2, '0')}</span>
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
