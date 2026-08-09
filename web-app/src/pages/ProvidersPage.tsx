import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ModelCatalogSection from '../sections/ModelCatalogSection';
import FailoverSection from '../sections/FailoverSection';

const PROVIDERS = ['openai', 'anthropic', 'google', 'azure', 'mistral', 'cohere', 'meta', 'groq'];

function HealthGridVisual() {
  return (
    <div className="opa-card" style={{ padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
        <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>provider health</span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 500, color: 'var(--accent)' }}>8/8</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
        {PROVIDERS.map(p => (
          <div key={p} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
            <span className="live-dot-static" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)' }} />
            <span style={{ fontSize: 10.5, color: 'var(--ink-3)' }}>{p}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ProvidersPage() {
  useEffect(() => { document.title = 'Providers · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Providers"
        title={<>One API. <span style={{ color: 'var(--accent)' }}>Every model,</span> no lock-in.</>}
        description="The full model catalog, and what actually happens when a provider key goes down — beyond the live health grid on the homepage."
        visual={<HealthGridVisual />}
      />
      <ModelCatalogSection />
      <FailoverSection />
    </>
  );
}
