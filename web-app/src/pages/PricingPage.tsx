import { useEffect } from 'react';
import PricingSection from '../sections/PricingSection';

export default function PricingPage() {
  useEffect(() => { document.title = 'Pricing · OpenProxyAI'; }, []);

  return <PricingSection />;
}
