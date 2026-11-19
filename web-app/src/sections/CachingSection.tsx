import Section from '../components/Section';

const TIERS = [
  { n: '1', name: 'Exact repeats', desc: 'Remembers identical questions on each server and answers them instantly.' },
  { n: '2', name: 'Shared memory', desc: 'Shares those answers across all your servers, so the saving grows with usage.' },
  { n: '3', name: 'Similar questions', desc: 'Recognizes questions that mean the same thing, even when the wording differs.' },
];

export default function CachingSection() {
  return (
    <Section id="caching" label="Cost savings" title={<>Do not pay twice <em>for the same answer.</em></>} aside="optional">
      <div className="grid-3">
        {TIERS.map(t => (
          <div key={t.n} className="opa-card" style={{ padding: 22 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
              <span style={{ fontSize: 22, fontWeight: 600, color: 'var(--ink)' }}>{t.n}</span>
              <span style={{ color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{t.name}</span>
            </div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{t.desc}</p>
          </div>
        ))}
      </div>
      <p className="note">You turn reuse on when you are ready. Your policy is always applied first, so a refused request is never answered from memory.</p>
    </Section>
  );
}
