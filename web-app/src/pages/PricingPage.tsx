import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PricingSection from '../sections/PricingSection';
import BuildVsBuySection from '../sections/BuildVsBuySection';
import PricingFaqSection from '../sections/PricingFaqSection';

export default function PricingPage() {
  useEffect(() => { document.title = 'Pricing | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Pricing"
        title={<>Open source first. <span style={{ color: 'var(--accent)' }}>Plans lift limits.</span></>}
        description="OpenProxyAI is Apache-2.0 and free to self-host. The plans below change how many users, keys and days of audit history one deployment allows, plus SSO and compliance templates. Nothing else is behind a paywall in the code."
      />
      <PricingSection />
      <BuildVsBuySection />
      <PricingFaqSection />
    </>
  );
}
