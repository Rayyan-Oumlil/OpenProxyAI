import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PageCta from '../components/PageCta';
import PricingSection from '../sections/PricingSection';
import PlansTableSection from '../sections/PlansTableSection';
import BuildVsBuySection from '../sections/BuildVsBuySection';
import PricingFaqSection from '../sections/PricingFaqSection';

export default function PricingPage() {
  useEffect(() => { document.title = 'Pricing | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        secondary={{ label: 'Compare the plans', href: '#plans' }}
        eyebrow="Pricing"
        title={<>Open source first. <span style={{ color: 'var(--soft)' }}>Plans lift limits.</span></>}
        description="OpenProxyAI is Apache-2.0 and free to self-host. The plans below change how many users, keys and days of audit history one deployment allows, plus single sign-on and compliance templates. Nothing else is behind a paywall."
      />
      <PricingSection />
      <PlansTableSection />
      <BuildVsBuySection />
      <PricingFaqSection />
      <PageCta title="Get an answer for your organization." body="Tell us how many people and teams you need to cover, and we will come back with the right plan." />
    </>
  );
}
