import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import BuildVsBuySection from '../sections/BuildVsBuySection';
import PricingFaqSection from '../sections/PricingFaqSection';

export default function PricingPage() {
  useEffect(() => { document.title = 'Pricing · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Pricing"
        title={<>What this replaces on <span style={{ color: 'var(--accent)' }}>your roadmap.</span></>}
        description="Plans and the flat-fee breakdown live on the homepage — this page is the build-vs-buy math and the billing questions that actually come up."
      />
      <BuildVsBuySection />
      <PricingFaqSection />
    </>
  );
}
