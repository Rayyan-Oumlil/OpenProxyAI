import Section from '../components/Section';

const PROVIDERS = [
  { provider: 'OpenAI and Azure OpenAI', note: 'Hosted models and regional Azure deployments.' },
  { provider: 'Anthropic', note: 'Claude models through the Anthropic API.' },
  { provider: 'Google, Mistral, Cohere, Groq', note: 'Hosted APIs, each with its own provider key.' },
  { provider: 'Your own endpoint', note: 'Any OpenAI-compatible server, including a local model. Mark it internal and the gateway guards every connection to it.' },
  { provider: '100+ more through LiteLLM', note: 'The gateway uses LiteLLM as its provider layer, so its supported providers work.' },
];

export default function ModelCatalogSection() {
  return (
    <Section id="catalog" label="§01 · providers" title={<>Many providers, <em>one integration.</em></>} aside="model names come from the provider">
      <div className="opa-card">
        {PROVIDERS.map((c, i) => (
          <div key={c.provider} className="data-row prov-row" style={{ display: 'grid', gridTemplateColumns: 'minmax(120px,260px) minmax(0,1fr)', gap: 16, padding: '14px 18px', borderBottom: i < PROVIDERS.length - 1 ? '1px solid var(--line)' : 'none', fontSize: 13 }}>
            <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{c.provider}</span>
            <span style={{ color: 'var(--ink-2)' }}>{c.note}</span>
          </div>
        ))}
      </div>
      <p className="note">
        Your app targets a model name, not a provider. Which provider key serves it is configuration, and with data-class routing on, it is also a decision your registry makes. We list no model ids here because they change faster than this page.
      </p>
      <style>{`@media (max-width: 700px) { .prov-row { grid-template-columns: minmax(0,1fr) !important; gap: 4px !important; } }`}</style>
    </Section>
  );
}
