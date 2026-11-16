import Section from '../components/Section';

const TIERS = [
  { n: 'L1', name: 'In-memory', desc: 'A per-instance cache for exact repeat requests inside one gateway process.', flag: 'SEMANTIC_CACHE_ENABLED' },
  { n: 'L2', name: 'Redis', desc: 'A shared exact-match cache across every gateway instance. It survives restarts and scales horizontally.', flag: 'CACHE_ENABLED' },
  { n: 'L3', name: 'Semantic (pgvector)', desc: 'Embeds each prompt and matches on similarity, so it can answer a paraphrase the first two tiers miss.', flag: 'SEMANTIC_CACHE_ENABLED' },
];

export default function CachingSection() {
  return (
    <Section id="caching" label="§04 · caching" title={<>Three tiers. <em>Fewer duplicate calls,</em> lower cost.</>} aside="off by default · checked in order">
      <div className="grid-3">
        {TIERS.map(t => (
          <div key={t.n} className="opa-card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 20, fontWeight: 500, color: 'var(--accent)' }}>{t.n}</span>
              <span style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500 }}>{t.name}</span>
            </div>
            <p style={{ margin: '0 0 10px', fontFamily: 'var(--sans)', fontSize: 13.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{t.desc}</p>
            <code style={{ fontSize: 11, color: 'var(--ink-3)' }}>{t.flag}</code>
          </div>
        ))}
      </div>
      <p className="note">Caching is off until you enable it. Policy runs before the cache, so a refused request is never answered from an old entry. We list no hit latencies: they depend on your hardware and we have no reproducible benchmark yet.</p>
    </Section>
  );
}
