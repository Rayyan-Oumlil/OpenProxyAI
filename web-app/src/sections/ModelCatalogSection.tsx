import { PAGE_MAX_WIDTH } from '../lib/layout';

const CATALOG = [
  { provider: 'OpenAI', models: 'gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o1-mini' },
  { provider: 'Anthropic', models: 'claude-3.5-sonnet, claude-3.5-haiku, claude-3-opus' },
  { provider: 'Google', models: 'gemini-1.5-pro, gemini-1.5-flash, gemini-1.0-pro' },
  { provider: 'Azure OpenAI', models: 'gpt-4o, gpt-4-turbo (regional deployments)' },
  { provider: 'Mistral', models: 'mistral-large-2, mistral-small, codestral' },
  { provider: 'Cohere', models: 'command-r+, command-r, embed-v3' },
  { provider: 'Meta (via provider)', models: 'llama-3-70b, llama-3-8b' },
  { provider: 'Groq', models: 'mixtral-8x7b, llama-3-70b (low-latency inference)' },
];

export default function ModelCatalogSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§01 · catalog</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Every major provider, <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>one integration.</em>
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>updated as providers ship</span>
        </div>

        <div className="opa-card">
          {CATALOG.map((c, i) => (
            <div key={c.provider} style={{
              display: 'grid', gridTemplateColumns: '200px 1fr', gap: 16, padding: '14px 18px',
              borderBottom: i < CATALOG.length - 1 ? '1px solid var(--line)' : 'none', fontSize: 13,
            }} className="data-row">
              <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{c.provider}</span>
              <span style={{ color: 'var(--ink-2)' }}>{c.models}</span>
            </div>
          ))}
        </div>

        <p style={{ color: 'var(--ink-3)', fontSize: 12, margin: '14px 0 0' }}>
          Your app targets a model name, not a provider — switching which provider serves a model is a config change, not a code change.
        </p>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
