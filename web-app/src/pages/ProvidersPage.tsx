import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ModelCatalogSection from '../sections/ModelCatalogSection';
import FailoverSection from '../sections/FailoverSection';

export default function ProvidersPage() {
  useEffect(() => { document.title = 'Providers · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Providers"
        title={<>One API. <span style={{ color: 'var(--accent)' }}>Every model,</span> no lock-in.</>}
        description="The full model catalog, and what actually happens when a provider key goes down — beyond the live health grid on the homepage."
      />
      <ModelCatalogSection />
      <FailoverSection />
    </>
  );
}
