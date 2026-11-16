import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ChecklistCard from '../components/ChecklistCard';
import ModelCatalogSection from '../sections/ModelCatalogSection';
import FailoverSection from '../sections/FailoverSection';

export default function ProvidersPage() {
  useEffect(() => { document.title = 'Integrations and models | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Integrations"
        title={<>The AI models you use, <span style={{ color: 'var(--accent)' }}>under your rules.</span></>}
        description="Connect hosted AI providers and models you run yourself through one governed layer. Each connection carries your rules: its region, the highest sensitivity it may handle and its share of traffic."
        visual={
          <ChecklistCard
            title="Each connection carries"
            items={[
              { text: 'The region where it may process data', ok: true },
              { text: 'The highest sensitivity it may handle', ok: true },
              { text: 'Its share of traffic among healthy accounts', ok: true },
              { text: 'An optional private address for your own models', ok: true },
            ]}
          />
        }
      />
      <ModelCatalogSection />
      <FailoverSection />
    </>
  );
}
