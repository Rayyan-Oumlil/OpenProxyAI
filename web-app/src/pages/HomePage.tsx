import { useEffect } from 'react';
import HeroSection from '../sections/HeroSection';
import PipelineSection from '../sections/PipelineSection';
import RouterSection from '../sections/RouterSection';
import BudgetsPoliciesSection from '../sections/BudgetsPoliciesSection';
import DeploySection from '../sections/DeploySection';
import PricingSection from '../sections/PricingSection';

export default function HomePage() {
  useEffect(() => { document.title = 'OpenProxyAI · The control plane for enterprise AI'; }, []);

  return (
    <>
      <HeroSection />
      <PipelineSection />
      <RouterSection />
      <BudgetsPoliciesSection />
      <DeploySection />
      <PricingSection />
    </>
  );
}
