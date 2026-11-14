import { useEffect } from 'react';
import HeroSection from '../sections/HeroSection';
import PipelineSection from '../sections/PipelineSection';
import RouterSection from '../sections/RouterSection';
import BudgetsPoliciesSection from '../sections/BudgetsPoliciesSection';
import DeploySection from '../sections/DeploySection';
import PricingSection from '../sections/PricingSection';
import MobileExplore from '../sections/MobileExplore';

export default function HomePage() {
  useEffect(() => { document.title = 'OpenProxyAI | Open-source LLM gateway for enterprise AI'; }, []);

  return (
    <>
      <HeroSection />
      <PipelineSection />
      {/* Phones get the short version: the detail lives on its own page, so the home page stays scannable. */}
      <div className="hidden lg:block">
        <RouterSection />
      </div>
      <BudgetsPoliciesSection />
      <div className="hidden lg:block">
        <DeploySection />
        <PricingSection />
      </div>
      <MobileExplore />
    </>
  );
}
