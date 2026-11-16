import Section from '../components/Section';

const PROVIDERS = [
  { provider: 'OpenAI and Azure OpenAI', note: 'Hosted models and regional Azure deployments.' },
  { provider: 'Anthropic', note: 'Claude models through Anthropic.' },
  { provider: 'Google, Mistral, Cohere, Groq', note: 'Hosted AI services, each with your own account.' },
  { provider: 'Models you run yourself', note: 'Any OpenAI-compatible service in your own environment, including a local model. Connections to it are checked every time.' },
  { provider: 'Over a hundred more', note: 'Most other AI providers are supported through an open-source compatibility layer.' },
];

export default function ModelCatalogSection() {
  return (
    <Section id="catalog" label="Models" title={<>Many providers, <em>one place to govern them.</em></>} aside="model names come from the provider">
      <div className="opa-card">
        {PROVIDERS.map((c, i) => (
          <div key={c.provider} className="data-row prov-row" style={{ display: 'grid', gridTemplateColumns: 'minmax(120px,280px) minmax(0,1fr)', gap: 16, padding: '16px 20px', borderBottom: i < PROVIDERS.length - 1 ? '1px solid var(--line)' : 'none', fontSize: 14.5 }}>
            <span style={{ color: 'var(--ink)', fontWeight: 600 }}>{c.provider}</span>
            <span style={{ color: 'var(--ink-2)' }}>{c.note}</span>
          </div>
        ))}
      </div>
      <p className="note">
        Your applications ask for a model by name, and you decide which provider account serves it. We list no model names here because they change faster than this page.
      </p>
      <style>{`@media (max-width: 700px) { .prov-row { grid-template-columns: minmax(0,1fr) !important; gap: 4px !important; } }`}</style>
    </Section>
  );
}
