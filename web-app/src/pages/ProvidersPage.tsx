import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import RouterSection from '../sections/RouterSection';

export default function ProvidersPage() {
  useEffect(() => { document.title = 'Providers · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Providers"
        title={<>One API. <span style={{ color: 'var(--accent)' }}>Every model,</span> no lock-in.</>}
        description="Switch providers, add a fallback, or split traffic across regions without touching application code. Each provider can hold multiple keys, rotated by weight, filtered by data-residency region."
      />
      <RouterSection />
    </>
  );
}
