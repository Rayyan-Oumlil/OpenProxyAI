import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ArchitectureSection from '../sections/ArchitectureSection';
import CachingSection from '../sections/CachingSection';
import ObservabilitySection from '../sections/ObservabilitySection';

export default function ProductPage() {
  useEffect(() => { document.title = 'Product · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product"
        title={<>How the <span style={{ color: 'var(--accent)' }}>control plane</span> works.</>}
        description="Beyond the request pipeline on the homepage — this is the architecture, the cache, and how it plugs into the observability stack you already run."
      />
      <ArchitectureSection />
      <CachingSection />
      <ObservabilitySection />
    </>
  );
}
