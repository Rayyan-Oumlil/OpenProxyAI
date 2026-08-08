import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PipelineSection from '../sections/PipelineSection';
import CachingSection from '../sections/CachingSection';
import DeploySection from '../sections/DeploySection';

export default function ProductPage() {
  useEffect(() => { document.title = 'Product · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product"
        title={<>How the <span style={{ color: 'var(--accent)' }}>control plane</span> works.</>}
        description="Every request from your org passes through the same pipeline — authenticated, rate-limited, policy-checked, cached, routed, and logged — before it ever reaches a provider."
      />
      <PipelineSection />
      <CachingSection />
      <DeploySection />
    </>
  );
}
